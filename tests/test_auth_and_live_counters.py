import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import Config
from app import create_app
from app.extensions import db
from app.models import Bank, Exam, ExamSession, User
from app.realtime.manager import session_manager


@pytest.fixture()
def app_ctx(tmp_path):
    Config.SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path/'test_auth.db'}"
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.app_context():
        db.drop_all()
        db.create_all()
        teacher = User(
            username='Profesor Demo',
            first_name='Profesor',
            last_name='Demo',
            email='teacher@example.com',
            phone='123456789',
            institution='Universidad Nacional',
            role='instructor'
        )
        teacher.set_password('secret123')
        db.session.add(teacher)
        db.session.commit()
        yield app, teacher


def login(client, email, password='secret123'):
    return client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)


def test_register_student_success(app_ctx):
    app, _ = app_ctx
    client = app.test_client()

    # GET register page
    res_get = client.get('/register')
    assert res_get.status_code == 200
    assert b'Crear Nueva Cuenta' in res_get.data

    # POST student registration
    payload = {
        'first_name': 'Carlos',
        'last_name': 'Gomez',
        'email': 'carlos.gomez@test.com',
        'password': 'password123',
        'password_confirm': 'password123',
        'phone': '+57 310 999 8888',
        'institution': 'Instituto Técnico Central',
        'role': 'student'
    }
    res_post = client.post('/register', data=payload, follow_redirects=True)
    assert res_post.status_code == 200

    with app.app_context():
        user = User.query.filter_by(email='carlos.gomez@test.com').first()
        assert user is not None
        assert user.first_name == 'Carlos'
        assert user.last_name == 'Gomez'
        assert user.full_name == 'Carlos Gomez'
        assert user.phone == '+57 310 999 8888'
        assert user.institution == 'Instituto Técnico Central'
        assert user.role == 'student'
        assert user.check_password('password123')
        assert Bank.query.filter_by(created_by=user.id).count() == 0


def test_register_instructor_success(app_ctx):
    app, _ = app_ctx
    client = app.test_client()

    payload = {
        'first_name': 'Maria',
        'last_name': 'Rodriguez',
        'email': 'maria.profesora@test.com',
        'password': 'password123',
        'password_confirm': 'password123',
        'phone': '3001234567',
        'institution': 'Colegio Mayor',
        'role': 'instructor'
    }
    res_post = client.post('/register', data=payload, follow_redirects=True)
    assert res_post.status_code == 200

    with app.app_context():
        user = User.query.filter_by(email='maria.profesora@test.com').first()
        assert user is not None
        assert user.first_name == 'Maria'
        assert user.last_name == 'Rodriguez'
        assert user.phone == '3001234567'
        assert user.institution == 'Colegio Mayor'
        assert user.role == 'instructor'
        assert user.check_password('password123')

        default_banks = Bank.query.filter_by(created_by=user.id).all()
        assert len(default_banks) == 1
        assert default_banks[0].name == f"Mi Banco de Preguntas #{user.id}"


def test_register_two_instructors_each_get_their_own_default_bank(app_ctx):
    """Dos profesores nuevos no deben chocar por el nombre único del banco."""
    app, _ = app_ctx
    client = app.test_client()

    for idx, email in enumerate(['prof.a@test.com', 'prof.b@test.com']):
        payload = {
            'first_name': f'Prof{idx}',
            'last_name': 'Test',
            'email': email,
            'password': 'password123',
            'password_confirm': 'password123',
            'role': 'instructor'
        }
        res = client.post('/register', data=payload, follow_redirects=True)
        assert res.status_code == 200
        client.get('/logout')

    with app.app_context():
        users = User.query.filter(User.email.in_(['prof.a@test.com', 'prof.b@test.com'])).all()
        assert len(users) == 2
        for user in users:
            banks = Bank.query.filter_by(created_by=user.id).all()
            assert len(banks) == 1


def test_register_validation_duplicate_email_and_password_mismatch(app_ctx):
    app, teacher = app_ctx
    client = app.test_client()

    # 1. Duplicate email test
    payload_dup = {
        'first_name': 'Otro',
        'last_name': 'Profesor',
        'email': 'teacher@example.com', # already exists
        'password': 'password123',
        'password_confirm': 'password123',
        'role': 'instructor'
    }
    res_dup = client.post('/register', data=payload_dup, follow_redirects=True)
    assert res_dup.status_code == 200
    assert b'Ya existe una cuenta registrada con el correo' in res_dup.data

    # 2. Mismatched passwords
    payload_mismatch = {
        'first_name': 'Ana',
        'last_name': 'Lopez',
        'email': 'ana.lopez@test.com',
        'password': 'password123',
        'password_confirm': 'different_pwd',
        'role': 'student'
    }
    res_mismatch = client.post('/register', data=payload_mismatch, follow_redirects=True)
    assert res_mismatch.status_code == 200
    assert b'Las contrase' in res_mismatch.data


def test_active_sessions_and_live_student_counter(app_ctx):
    app, teacher = app_ctx
    client = app.test_client()

    with app.app_context():
        # Create 2 exams and 2 active sessions for teacher
        exam1 = Exam(title='Examen Redes 1', instructor_id=teacher.id)
        exam2 = Exam(title='Examen Algoritmos 2', instructor_id=teacher.id)
        db.session.add_all([exam1, exam2])
        db.session.commit()

        session1 = ExamSession(exam_id=exam1.id, session_code='RED101', status='RUNNING')
        session2 = ExamSession(exam_id=exam2.id, session_code='ALG202', status='READY')
        db.session.add_all([session1, session2])
        db.session.commit()

        # Connect simulated students in memory session_manager
        rt_s1 = session_manager.get_or_create_by_db_session(session1)
        session_manager.add_student('RED101', 101, 'Alumno 1', 'sid_1')
        session_manager.add_student('RED101', 102, 'Alumno 2', 'sid_2')

        rt_s2 = session_manager.get_or_create_by_db_session(session2)
        session_manager.add_student('ALG202', 103, 'Alumno 3', 'sid_3')

    # Login as teacher
    login(client, 'teacher@example.com', 'secret123')

    # Query active sessions summary
    res = client.get('/instructor/active-sessions-summary')
    assert res.status_code == 200
    data = res.get_json()

    assert data['total_active_sessions'] == 2
    assert data['total_connected_students'] == 3

    codes = [s['session_code'] for s in data['sessions']]
    assert 'RED101' in codes
    assert 'ALG202' in codes

    red_s = next(s for s in data['sessions'] if s['session_code'] == 'RED101')
    assert red_s['connected_count'] == 2
    assert red_s['exam_title'] == 'Examen Redes 1'

    # Check dashboard renders active summary
    res_dash = client.get('/instructor/dashboard')
    assert res_dash.status_code == 200
    assert b'RED101' in res_dash.data
    assert b'ALG202' in res_dash.data
    assert b'Monitor de Salas en Vivo' in res_dash.data
