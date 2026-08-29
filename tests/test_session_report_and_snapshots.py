import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import Config
from app import create_app
from app.extensions import db
from app.models import Bank, Exam, ExamQuestion, ExamSession, Question, QuestionOption, SessionQuestionSnapshot, User, ExamAttempt, StudentAnswer


@pytest.fixture()
def app_ctx(tmp_path):
    Config.SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path/'test_report.db'}"
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.app_context():
        db.drop_all()
        db.create_all()
        teacher = User(username='ProfesorX', email='profx@example.com', role='instructor')
        teacher.set_password('secret')
        student = User(username='Alumno1', email='alumno1@example.com', role='student')
        student.set_password('secret')
        db.session.add_all([teacher, student])
        db.session.commit()
        yield app, teacher, student


def login(client, email, password='secret'):
    return client.post('/login', data={'email': email, 'password': password})


def test_question_snapshot_integrity_when_question_is_modified(app_ctx):
    """
    Test that questions are snapshotted on session creation.
    When a student submits answers, and later the teacher modifies the question in the bank,
    the session report still shows the original question and student's answer, NOT the modified one.
    """
    app, teacher, student = app_ctx
    
    with app.app_context():
        # 1. Crear banco y pregunta inicial
        bank = Bank(name="Banco Redes", created_by=teacher.id)
        db.session.add(bank)
        db.session.commit()

        q1 = Question(
            bank_id=bank.id,
            question_type='multiple_choice',
            statement="¿Cuál es el puerto HTTP original?",
            default_points=5.0,
            feedback_text="El puerto 80 es la norma HTTP."
        )
        db.session.add(q1)
        db.session.commit()

        opt1 = QuestionOption(question_id=q1.id, option_text="80", is_correct=True)
        opt2 = QuestionOption(question_id=q1.id, option_text="443", is_correct=False)
        db.session.add_all([opt1, opt2])
        db.session.commit()

        # 2. Crear examen y asociar pregunta
        exam = Exam(title="Examen Redes V1", instructor_id=teacher.id, duration_minutes=20, passing_score=60.0)
        db.session.add(exam)
        db.session.commit()

        eq = ExamQuestion(exam_id=exam.id, question_id=q1.id, points=5.0, order_index=1)
        db.session.add(eq)
        db.session.commit()

        exam_id = exam.id
        q1_id = q1.id
        opt1_id = opt1.id

    c = app.test_client()

    # 3. Profesor inicia la sesión (crea la sala)
    login(c, 'profx@example.com')
    res_session = c.post(f'/instructor/session/start/{exam_id}', data={'expected_students': 1}, follow_redirects=True)
    assert res_session.status_code == 200

    with app.app_context():
        session_obj = ExamSession.query.filter_by(exam_id=exam_id).first()
        assert session_obj is not None
        session_id = session_obj.id

        # Verificar que se creó el snapshot de la pregunta
        snapshots = SessionQuestionSnapshot.query.filter_by(session_id=session_id).all()
        assert len(snapshots) == 1
        assert snapshots[0].statement == "¿Cuál es el puerto HTTP original?"
        assert snapshots[0].points == 5.0
        assert len(snapshots[0].options_data) == 2

    # 4. Alumno presenta el examen y responde la opción correcta original (80)
    login(c, 'alumno1@example.com')
    res_submit = c.post(f'/exam/submit/{session_id}', data={f'question_{q1_id}': str(opt1_id)}, follow_redirects=True)
    assert res_submit.status_code == 200

    with app.app_context():
        attempt = ExamAttempt.query.filter_by(session_id=session_id).first()
        assert attempt is not None
        assert attempt.score == 100.0
        assert len(attempt.answers) == 1
        ans = attempt.answers[0]
        assert ans.is_correct is True
        assert ans.display_statement == "¿Cuál es el puerto HTTP original?"
        assert ans.display_student_answer == "80"

    # 5. EL PROFESOR EDITA LA PREGUNTA EN EL BANCO
    # Cambia el enunciado a "¿Cuál es el puerto HTTPS modificado?", cambia las opciones y los puntos
    with app.app_context():
        q_mod = db.session.get(Question, q1_id)
        q_mod.statement = "¿Cuál es el puerto HTTPS modificado?"
        q_mod.default_points = 10.0
        # Modificar las opciones
        for o in q_mod.options:
            if o.option_text == "80":
                o.option_text = "8080 (modificado)"
                o.is_correct = False
            elif o.option_text == "443":
                o.option_text = "443 (ahora correcta)"
                o.is_correct = True
        db.session.commit()

        # Verificar que en el banco la pregunta efectivamente cambió
        q_check = db.session.get(Question, q1_id)
        assert q_check.statement == "¿Cuál es el puerto HTTPS modificado?"

    # 6. El profesor accede al reporte de la sesión (session_report.html)
    login(c, 'profx@example.com')
    res_report = c.get(f'/instructor/session/{session_id}/report')
    assert res_report.status_code == 200

    # DEBE MOSTRAR EL ENUNCIADO ORIGINAL CONGELADO (SNAPSHOT) Y NO EL MODIFICADO
    html_content = res_report.data.decode('utf-8')
    assert "¿Cuál es el puerto HTTP original?" in html_content
    assert "¿Cuál es el puerto HTTPS modificado?" not in html_content
    assert "80" in html_content
    assert "Matriz de Resultados" in html_content
    assert "Desglose por Pregunta (Snapshots)" in html_content
    assert "Desglose por Estudiante" in html_content

    # 7. El archivo Excel descargado también debe tener la pregunta original
    res_excel = c.get(f'/instructor/session/{session_id}/results.xlsx')
    assert res_excel.status_code == 200
    assert res_excel.headers['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
