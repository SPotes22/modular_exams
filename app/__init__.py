# app/__init__.py
from flask import Flask
from sqlalchemy import inspect
from app.config import Config
from app.extensions import db, login_manager, socketio

def ensure_schema():
    inspector = inspect(db.engine)
    exam_columns = {col['name'] for col in inspector.get_columns('exams')} if inspector.has_table('exams') else set()
    session_columns = {col['name'] for col in inspector.get_columns('exam_sessions')} if inspector.has_table('exam_sessions') else set()
    with db.engine.begin() as conn:
        if 'exam_mode' not in exam_columns:
            conn.exec_driver_sql("ALTER TABLE exams ADD COLUMN exam_mode VARCHAR(30) DEFAULT 'instant_feedback'")
        if 'source_bank_id' not in exam_columns:
            conn.exec_driver_sql("ALTER TABLE exams ADD COLUMN source_bank_id INTEGER")
        if 'random_question_count' not in exam_columns:
            conn.exec_driver_sql("ALTER TABLE exams ADD COLUMN random_question_count INTEGER")
        if 'expected_students' not in session_columns:
            conn.exec_driver_sql("ALTER TABLE exam_sessions ADD COLUMN expected_students INTEGER DEFAULT 0")

def init_db():
    from app.models import User, Bank, Question, QuestionOption, Exam, ExamQuestion
    db.create_all()
    ensure_schema()
    
    if not User.query.filter_by(role='instructor').first():
        teacher = User(username="Profesor Principal", email="profesor@capacitacion.com", role="instructor")
        teacher.set_password("admin123")
        db.session.add(teacher)
        db.session.commit()

        bank = Bank(name="Banco Inicial", description="Preguntas por defecto", created_by=teacher.id)
        db.session.add(bank)
        db.session.commit()

        q1 = Question(
            bank_id=bank.id,
            question_type='multiple_choice',
            statement="¿Cuál es el puerto predeterminado del protocolo HTTP?",
            category="Redes",
            feedback_text="El puerto 80 es la norma para tráfico web no cifrado."
        )
        q2 = Question(
            bank_id=bank.id,
            question_type='multiple_choice',
            statement="¿Qué protocolo de transporte es orientado a conexión?",
            category="Redes",
            feedback_text="TCP garantiza el establecimiento de enlace mediante handshake."
        )
        db.session.add_all([q1, q2])
        db.session.commit()

        db.session.add_all([
            QuestionOption(question_id=q1.id, option_text="80", is_correct=True),
            QuestionOption(question_id=q1.id, option_text="443", is_correct=False),
            QuestionOption(question_id=q2.id, option_text="TCP", is_correct=True),
            QuestionOption(question_id=q2.id, option_text="UDP", is_correct=False),
        ])

        exam = Exam(title="Examen Diagnóstico de Redes", duration_minutes=15, instructor_id=teacher.id)
        db.session.add(exam)
        db.session.commit()

        db.session.add_all([
            ExamQuestion(exam_id=exam.id, question_id=q1.id, points=5.0),
            ExamQuestion(exam_id=exam.id, question_id=q2.id, points=5.0)
        ])
        db.session.commit()
        print("Base de datos inicializada correctamente.")


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Inicializar extensiones
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    socketio.init_app(app)

    with app.app_context():
        init_db()

    # Registrar Blueprints (Iremos creando las carpetas en el siguiente paso)
    from app.blueprints.auth import auth_bp
    from app.blueprints.questions import questions_bp
    from app.blueprints.exams import exams_bp
    from app.blueprints.media import media_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(questions_bp)
    app.register_blueprint(exams_bp)
    app.register_blueprint(media_bp)

    return app
