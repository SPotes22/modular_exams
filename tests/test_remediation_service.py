import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import Config
from app import create_app
from app.extensions import db
from app.models import (
    Bank, Exam, ExamQuestion, ExamSession, Question, QuestionOption,
    User, ExamAttempt, StudentAnswer, Learning, LearningProgress
)
from app.services.remediation_service import RemediationService


@pytest.fixture()
def app_ctx(tmp_path):
    Config.SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path/'test_remediation.db'}"
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app


def _seed_failing_session(app):
    with app.app_context():
        teacher = User(username='Profe', email='profe@example.com', role='instructor')
        teacher.set_password('secret')
        student = User(username='Alumno', email='alumno@example.com', role='student')
        student.set_password('secret')
        db.session.add_all([teacher, student])
        db.session.commit()

        bank = Bank(name="Banco Redes", created_by=teacher.id)
        db.session.add(bank)
        db.session.commit()

        q1 = Question(
            bank_id=bank.id,
            question_type='multiple_choice',
            statement="¿Cuál es el puerto predeterminado del protocolo HTTP?",
            category="Redes",
            feedback_text="El puerto 80 es la norma para tráfico web no cifrado."
        )
        db.session.add(q1)
        db.session.commit()

        opt_correct = QuestionOption(question_id=q1.id, option_text="80", is_correct=True)
        opt_wrong = QuestionOption(question_id=q1.id, option_text="443", is_correct=False)
        db.session.add_all([opt_correct, opt_wrong])
        db.session.commit()

        exam = Exam(title="Examen Diagnóstico de Redes", instructor_id=teacher.id, duration_minutes=15)
        db.session.add(exam)
        db.session.commit()

        eq = ExamQuestion(exam_id=exam.id, question_id=q1.id, points=5.0, order_index=1)
        db.session.add(eq)
        db.session.commit()

        session = ExamSession(exam_id=exam.id, session_code="ABC123", status="FINISHED")
        db.session.add(session)
        db.session.commit()

        attempt = ExamAttempt(
            student_id=student.id, session_id=session.id, attempt_number=1,
            score=0.0, earned_points=0.0, max_points=5.0, status='completed'
        )
        db.session.add(attempt)
        db.session.commit()

        answer = StudentAnswer(
            attempt_id=attempt.id, question_id=q1.id, selected_option_id=opt_wrong.id,
            question_statement=q1.statement, selected_option_text=opt_wrong.option_text,
            correct_answer_text=opt_correct.option_text, is_correct=False, points_awarded=0.0
        )
        db.session.add(answer)
        db.session.commit()

        return session.id


def test_build_remediation_course_generates_valid_learning(app_ctx):
    session_id = _seed_failing_session(app_ctx)

    with app_ctx.app_context():
        course = RemediationService.build_remediation_course(session_id)

        assert course is not None
        assert isinstance(course, Learning)
        assert course.estado == 'draft'
        assert "Refuerzo" in course.nombre

        assert len(course.modules) == 1
        module = course.modules[0]
        assert "Redes" in module.titulo

        assert len(module.lessons) == 1
        lesson = module.lessons[0]
        assert len(lesson.blocks) == 2

        text_block, quiz_block = lesson.blocks[0], lesson.blocks[1]
        assert text_block.tipo == 'text'
        assert "80" in text_block.configuracion["content"]

        assert quiz_block.tipo == 'question'
        cfg = quiz_block.configuracion
        assert cfg["question_type"] == "multiple_choice"
        correct_opts = [o for o in cfg["options"] if o["is_correct"]]
        assert len(correct_opts) == 1
        assert correct_opts[0]["text"] == "80"

        progress = LearningProgress.query.filter_by(learning_id=course.id).all()
        assert len(progress) == 1
        assert progress[0].user_id is not None


def _seed_pending_session(app, auto_remediation):
    """Como _seed_failing_session, pero el examen queda con auto_remediation
    configurable y la sesión SIN finalizar (para probar el disparo automático
    al finalizarla vía las rutas HTTP reales)."""
    with app.app_context():
        teacher = User(username='Profe2', email='profe2@example.com', role='instructor')
        teacher.set_password('secret')
        student = User(username='Alumno2', email='alumno2@example.com', role='student')
        student.set_password('secret')
        db.session.add_all([teacher, student])
        db.session.commit()

        bank = Bank(name="Banco Redes 2", created_by=teacher.id)
        db.session.add(bank)
        db.session.commit()

        q1 = Question(
            bank_id=bank.id, question_type='multiple_choice',
            statement="¿Qué protocolo es orientado a conexión?", category="Redes"
        )
        db.session.add(q1)
        db.session.commit()

        opt_correct = QuestionOption(question_id=q1.id, option_text="TCP", is_correct=True)
        opt_wrong = QuestionOption(question_id=q1.id, option_text="UDP", is_correct=False)
        db.session.add_all([opt_correct, opt_wrong])
        db.session.commit()

        exam = Exam(title="Examen Pendiente", instructor_id=teacher.id, auto_remediation=auto_remediation)
        db.session.add(exam)
        db.session.commit()

        eq = ExamQuestion(exam_id=exam.id, question_id=q1.id, points=5.0, order_index=1)
        db.session.add(eq)
        db.session.commit()

        session = ExamSession(exam_id=exam.id, session_code="PEND01", status="RUNNING")
        db.session.add(session)
        db.session.commit()

        attempt = ExamAttempt(
            student_id=student.id, session_id=session.id, attempt_number=1,
            score=0.0, earned_points=0.0, max_points=5.0, status='completed'
        )
        db.session.add(attempt)
        db.session.commit()

        answer = StudentAnswer(
            attempt_id=attempt.id, question_id=q1.id, selected_option_id=opt_wrong.id,
            selected_option_text=opt_wrong.option_text, correct_answer_text=opt_correct.option_text,
            is_correct=False, points_awarded=0.0
        )
        db.session.add(answer)
        db.session.commit()

        return session.id, 'profe2@example.com'


def _login(client, email, password='secret'):
    return client.post('/login', data={'email': email, 'password': password}, follow_redirects=True)


def test_finishing_session_via_lobby_auto_generates_course_when_enabled(app_ctx):
    session_id, email = _seed_pending_session(app_ctx, auto_remediation=True)
    client = app_ctx.test_client()
    _login(client, email)

    res = client.post(f'/instructor/session/{session_id}/finish', follow_redirects=True)
    assert res.status_code == 200

    with app_ctx.app_context():
        course = Learning.query.filter_by(source_session_id=session_id).first()
        assert course is not None
        assert course.estado == 'draft'
        course_nombre = course.nombre

    # Debe verse en la página de Capacitaciones del instructor sin publicar nada a mano.
    dash = client.get('/learning/instructor/dashboard')
    assert course_nombre.encode('utf-8') in dash.data


def test_finishing_session_does_not_generate_course_when_disabled(app_ctx):
    session_id, email = _seed_pending_session(app_ctx, auto_remediation=False)
    client = app_ctx.test_client()
    _login(client, email)

    client.post(f'/instructor/session/{session_id}/finish', follow_redirects=True)

    with app_ctx.app_context():
        assert Learning.query.filter_by(source_session_id=session_id).first() is None


def test_finish_then_close_does_not_duplicate_course(app_ctx):
    """Si por alguna razón se dispara la generación más de una vez para la misma
    sesión (dos rutas distintas de cierre), no debe crear dos capacitaciones."""
    session_id, email = _seed_pending_session(app_ctx, auto_remediation=True)
    client = app_ctx.test_client()
    _login(client, email)

    client.post(f'/instructor/session/{session_id}/finish', follow_redirects=True)
    client.post(f'/exam/close/{session_id}', follow_redirects=True)

    with app_ctx.app_context():
        courses = Learning.query.filter_by(source_session_id=session_id).all()
        assert len(courses) == 1


def test_exam_reports_lists_session_finished_with_uppercase_status(app_ctx):
    """Bug encontrado: /instructor/session/<id>/finish guarda status='FINISHED'
    (mayúsculas), pero /instructor/reports filtraba solo 'finished' (minúsculas) —
    la sesión desaparecía de la lista y el profesor nunca llegaba al botón manual."""
    session_id, email = _seed_pending_session(app_ctx, auto_remediation=False)
    client = app_ctx.test_client()
    _login(client, email)

    client.post(f'/instructor/session/{session_id}/finish', follow_redirects=True)

    res = client.get('/instructor/reports')
    assert res.status_code == 200
    assert b'PEND01' in res.data


def test_build_remediation_course_no_failing_students_returns_none(app_ctx):
    with app_ctx.app_context():
        teacher = User(username='Profe2', email='profe2@example.com', role='instructor')
        teacher.set_password('secret')
        db.session.add(teacher)
        db.session.commit()

        exam = Exam(title="Examen vacío", instructor_id=teacher.id)
        db.session.add(exam)
        db.session.commit()

        session = ExamSession(exam_id=exam.id, session_code="EMPTY1", status="FINISHED")
        db.session.add(session)
        db.session.commit()

        result = RemediationService.build_remediation_course(session.id)
        assert result is None
