import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import Config
from app import create_app
from app.extensions import db
from app.models import Exam, ExamSession, Payment, User
from app.services import billing

MERCHANT = '0x' + 'ab' * 20
TX_HASH = '0x' + '12' * 32


@pytest.fixture()
def app_ctx(tmp_path):
    Config.SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path/'test_billing.db'}"
    app = create_app()
    app.config.update(TESTING=True, AVAX_MERCHANT_ADDRESS=MERCHANT)
    with app.app_context():
        db.drop_all()
        db.create_all()
        teacher = User(username='Profe', email='profe@example.com', role='instructor',
                       trial_started_at=datetime.utcnow())
        teacher.set_password('secret123')
        db.session.add(teacher)
        db.session.commit()
        exam = Exam(title='Quiz', duration_minutes=10, instructor_id=teacher.id)
        db.session.add(exam)
        db.session.commit()
        yield app, teacher, exam


def login(client):
    return client.post('/login', data={'email': 'profe@example.com', 'password': 'secret123'})


def fake_rpc(tx=None, receipt=None):
    tx = tx if tx is not None else {
        'chainId': hex(43113), 'to': MERCHANT, 'from': '0x' + 'cd' * 20,
        'value': hex(billing.plan_price_wei('instructor')),
    }
    receipt = receipt if receipt is not None else {'status': '0x1'}
    return lambda method, params: tx if method == 'eth_getTransactionByHash' else receipt


def test_new_instructor_starts_on_trial(app_ctx):
    _, teacher, _ = app_ctx
    status = billing.plan_status(teacher)
    assert status['key'] == 'trial'
    assert status['active'] is True
    assert status['days_left'] == 14
    assert status['max_participants'] == 10
    assert status['max_rooms'] == 1


def test_expired_trial_blocks_new_rooms(app_ctx):
    app, teacher, exam = app_ctx
    teacher.trial_started_at = datetime.utcnow() - timedelta(days=15)
    db.session.commit()

    c = app.test_client()
    login(c)
    res = c.post(f'/instructor/session/start/{exam.id}', data={})
    assert res.status_code == 302
    assert '/suscripcion' in res.headers['Location']
    assert ExamSession.query.count() == 0


def test_trial_allows_only_one_simultaneous_room(app_ctx):
    app, _, exam = app_ctx
    c = app.test_client()
    login(c)
    first = c.post(f'/instructor/session/start/{exam.id}', data={})
    assert '/instructor/lobby/' in first.headers['Location']
    second = c.post(f'/instructor/session/start/{exam.id}', data={})
    assert '/suscripcion' in second.headers['Location']
    assert ExamSession.query.count() == 1


def test_room_capacity_follows_plan(app_ctx):
    _, teacher, exam = app_ctx
    session = ExamSession(exam_id=exam.id, session_code='ABC123', status='READY')
    db.session.add(session)
    db.session.commit()
    assert billing.room_capacity_error(session, 9) is None
    assert billing.room_capacity_error(session, 10) is not None

    teacher.plan = 'academia'
    teacher.plan_expires_at = datetime.utcnow() + timedelta(days=30)
    db.session.commit()
    assert billing.room_capacity_error(session, 79) is None
    assert billing.room_capacity_error(session, 80) is not None


def test_valid_payment_activates_plan(app_ctx, monkeypatch):
    _, teacher, _ = app_ctx
    monkeypatch.setattr(billing, '_rpc', fake_rpc())
    expires = billing.verify_and_activate(teacher, 'instructor', TX_HASH)
    assert teacher.plan == 'instructor'
    assert expires > datetime.utcnow() + timedelta(days=29)
    assert billing.plan_status(teacher)['max_rooms'] == 6
    assert Payment.query.filter_by(tx_hash=TX_HASH).count() == 1

    with pytest.raises(billing.PaymentError):
        billing.verify_and_activate(teacher, 'instructor', TX_HASH)


@pytest.mark.parametrize('tx', [
    {'chainId': hex(43114), 'to': MERCHANT, 'value': hex(10 ** 18)},       # mainnet
    {'chainId': hex(43113), 'to': '0x' + 'ee' * 20, 'value': hex(10 ** 18)},  # otra billetera
    {'chainId': hex(43113), 'to': MERCHANT, 'value': hex(1)},              # monto insuficiente
])
def test_invalid_payments_are_rejected(app_ctx, monkeypatch, tx):
    _, teacher, _ = app_ctx
    monkeypatch.setattr(billing, '_rpc', fake_rpc(tx=tx))
    with pytest.raises(billing.PaymentError):
        billing.verify_and_activate(teacher, 'instructor', TX_HASH)
    assert teacher.plan == 'trial'


def test_unconfirmed_payment_is_pending(app_ctx, monkeypatch):
    app, _, _ = app_ctx
    monkeypatch.setattr(billing, '_rpc', fake_rpc(receipt={}))
    c = app.test_client()
    login(c)
    res = c.post('/suscripcion/verificar', json={'plan': 'academia', 'tx_hash': TX_HASH})
    assert res.status_code == 400  # el monto del plan instructor no alcanza para academia

    monkeypatch.setattr(billing, '_rpc', lambda m, p: None)
    res = c.post('/suscripcion/verificar', json={'plan': 'instructor', 'tx_hash': TX_HASH})
    assert res.status_code == 202
    assert res.get_json()['pending'] is True


def test_subscription_page_renders(app_ctx):
    app, _, _ = app_ctx
    c = app.test_client()
    login(c)
    html = c.get('/suscripcion').get_data(as_text=True)
    assert 'Pagar con Core' in html
    assert MERCHANT in html
