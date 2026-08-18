import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import Config
from app import create_app
from app.extensions import db
from app.models import Bank, Exam, ExamAttempt, ExamQuestion, ExamSession, Question, User
from app.services.exam_builder import duplicate_question, save_question_payload


@pytest.fixture()
def app_ctx(tmp_path):
    Config.SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path/'test.db'}"
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.app_context():
        db.drop_all()
        db.create_all()
        teacher = User(username='Teacher', email='teacher@example.com', role='instructor')
        teacher.set_password('secret')
        other = User(username='Other', email='other@example.com', role='instructor')
        other.set_password('secret')
        student = User(username='Student', email='student@example.com', role='student')
        student.set_password('secret')
        db.session.add_all([teacher, other, student])
        db.session.commit()
        yield app, teacher, other, student


def login(client, email, password='secret'):
    return client.post('/login', data={'email': email, 'password': password})


def make_bank(teacher):
    bank = Bank(name=f'Banco {teacher.id}', created_by=teacher.id)
    db.session.add(bank)
    db.session.commit()
    return bank


def test_feedback_limit_and_question_type_change(app_ctx):
    app, teacher, *_ = app_ctx
    with app.app_context():
        bank = make_bank(teacher)
        q = Question(bank_id=bank.id, statement='Temp')
        db.session.add(q)
        with pytest.raises(ValueError):
            save_question_payload(q, {
                'statement': 'Pregunta', 'question_type': 'multiple_choice', 'default_points': '1',
                'feedback_text': 'x' * 3001, 'options[]': ['A', 'B'], 'correct_options[]': ['0']
            })
        class Form(dict):
            def getlist(self, key): return self.get(key, [])
        save_question_payload(q, Form({'statement': '¿Verdadero?', 'question_type': 'true_false', 'default_points': '2', 'feedback_text': 'x' * 3000, 'true_false_correct': 'false'}))
        db.session.commit()
        assert q.question_type == 'true_false'
        assert len(q.options) == 2
        assert q.default_points == 2


def test_exam_builder_add_duplicate_order_and_random_validation(app_ctx):
    app, teacher, *_ = app_ctx
    with app.app_context():
        bank = make_bank(teacher)
        q1 = Question(bank_id=bank.id, statement='Q1', default_points=1)
        q2 = Question(bank_id=bank.id, statement='Q2', default_points=5)
        exam = Exam(title='Exam', instructor_id=teacher.id)
        db.session.add_all([q1, q2, exam]); db.session.commit()
        exam_id, q1_id, q2_id = exam.id, q1.id, q2.id
    c = app.test_client(); login(c, 'teacher@example.com')
    assert c.post(f'/instructor/exam/{exam_id}/add-bank', data={'question_ids': [str(q1_id), str(q2_id)]}).status_code == 302
    with app.app_context():
        assert ExamQuestion.query.filter_by(exam_id=exam_id).count() == 2
    assert c.post(f'/instructor/exam/{exam_id}/question/{q1_id}/duplicate').status_code == 302
    with app.app_context():
        assert ExamQuestion.query.filter_by(exam_id=exam_id).count() == 3
    c.post(f'/instructor/exam/{exam_id}/add-bank', data={'random_count': 99})


def test_authorization_and_session_controls(app_ctx):
    app, teacher, other, *_ = app_ctx
    with app.app_context():
        exam = Exam(title='Private', instructor_id=teacher.id)
        db.session.add(exam); db.session.commit()
        exam_id = exam.id
    c = app.test_client(); login(c, 'other@example.com')
    assert c.get(f'/instructor/exam/{exam_id}/edit').status_code == 403
    c = app.test_client(); login(c, 'teacher@example.com')
    r = c.post(f'/instructor/session/configure/{exam_id}', data={'question_order': 'random'}, follow_redirects=False)
    assert r.status_code == 302
    with app.app_context():
        session = ExamSession.query.filter_by(exam_id=exam_id).first()
        assert session.question_order == 'random'
        assert c.post(f'/instructor/session/{session.id}/pause').status_code == 302
        db.session.refresh(session)
        assert session.status == 'PAUSED'
