# app/__init__.py
from flask import Flask
from sqlalchemy import inspect
from app.config import Config
from app.extensions import db, login_manager, socketio

def _add_column_if_missing(conn, table_columns, table_name, column_name, ddl):
    if column_name not in table_columns:
        conn.exec_driver_sql(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")


def ensure_schema():
    inspector = inspect(db.engine)
    table_names = set(inspector.get_table_names())
    exam_columns = {col['name'] for col in inspector.get_columns('exams')} if 'exams' in table_names else set()
    session_columns = {col['name'] for col in inspector.get_columns('exam_sessions')} if 'exam_sessions' in table_names else set()
    question_columns = {col['name'] for col in inspector.get_columns('questions')} if 'questions' in table_names else set()
    exam_question_columns = {col['name'] for col in inspector.get_columns('exam_questions')} if 'exam_questions' in table_names else set()
    attempt_columns = {col['name'] for col in inspector.get_columns('exam_attempts')} if 'exam_attempts' in table_names else set()
    answer_columns = {col['name'] for col in inspector.get_columns('student_answers')} if 'student_answers' in table_names else set()
    user_columns = {col['name'] for col in inspector.get_columns('users')} if 'users' in table_names else set()
    with db.engine.begin() as conn:
        _add_column_if_missing(conn, exam_columns, 'exams', 'exam_mode', "VARCHAR(30) DEFAULT 'instant_feedback'")
        _add_column_if_missing(conn, exam_columns, 'exams', 'source_bank_id', 'INTEGER')
        _add_column_if_missing(conn, exam_columns, 'exams', 'random_question_count', 'INTEGER')
        _add_column_if_missing(conn, exam_columns, 'exams', 'instructions', 'TEXT')
        _add_column_if_missing(conn, exam_columns, 'exams', 'group_id', 'INTEGER')
        _add_column_if_missing(conn, exam_columns, 'exams', 'status', "VARCHAR(20) DEFAULT 'DRAFT'")
        _add_column_if_missing(conn, exam_columns, 'exams', 'allow_multiple_attempts', 'BOOLEAN DEFAULT 0')
        _add_column_if_missing(conn, exam_columns, 'exams', 'max_attempts', 'INTEGER DEFAULT 1')
        _add_column_if_missing(conn, exam_columns, 'exams', 'created_at', 'DATETIME')
        _add_column_if_missing(conn, exam_columns, 'exams', 'updated_at', 'DATETIME')
        _add_column_if_missing(conn, session_columns, 'exam_sessions', 'expected_students', 'INTEGER DEFAULT 0')
        _add_column_if_missing(conn, session_columns, 'exam_sessions', 'question_order', "VARCHAR(20) DEFAULT 'original'")
        _add_column_if_missing(conn, question_columns, 'questions', 'default_points', 'FLOAT DEFAULT 1.0')
        _add_column_if_missing(conn, question_columns, 'questions', 'created_at', 'DATETIME')
        _add_column_if_missing(conn, question_columns, 'questions', 'updated_at', 'DATETIME')
        _add_column_if_missing(conn, exam_question_columns, 'exam_questions', 'order_index', 'INTEGER DEFAULT 1')
        _add_column_if_missing(conn, attempt_columns, 'exam_attempts', 'attempt_number', 'INTEGER DEFAULT 1')
        _add_column_if_missing(conn, attempt_columns, 'exam_attempts', 'earned_points', 'FLOAT DEFAULT 0')
        _add_column_if_missing(conn, attempt_columns, 'exam_attempts', 'max_points', 'FLOAT DEFAULT 0')
        _add_column_if_missing(conn, answer_columns, 'student_answers', 'answer_text', 'TEXT')
        _add_column_if_missing(conn, answer_columns, 'student_answers', 'points_awarded', 'FLOAT DEFAULT 0')
        _add_column_if_missing(conn, user_columns, 'users', 'default_exam_view', "VARCHAR(40) DEFAULT 'questions'")

def init_db():
    from app.models import User, Bank, Question, QuestionOption, Exam, ExamQuestion, ExamClass, ExamGroup, Learning, LearningModule, Lesson, Block, LearningProgress, BlockAnswer
    db.create_all()
    ensure_schema()

    # Inicializar o actualizar Superusuario desde configuración (.env)
    superuser_email = Config.SUPERUSER_EMAIL
    superuser_pass = Config.SUPERUSER_PASSWORD
    superuser_name = Config.SUPERUSER_USERNAME

    superuser = User.query.filter((User.email == superuser_email) | (User.role == 'superuser')).first()
    if not superuser:
        superuser = User(username=superuser_name, email=superuser_email, role='superuser')
        superuser.set_password(superuser_pass)
        db.session.add(superuser)
        db.session.commit()
        print(f"Superusuario '{superuser_name}' ({superuser_email}) creado exitosamente.")
    else:
        superuser.role = 'superuser'
        superuser.email = superuser_email
        superuser.username = superuser_name
        superuser.set_password(superuser_pass)
        db.session.commit()
    
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

    # Registrar Blueprints
    from app.blueprints.auth import auth_bp
    from app.blueprints.questions import questions_bp
    from app.blueprints.exams import exams_bp
    from app.blueprints.media import media_bp
    from app.blueprints.admin import admin_bp
    from app.blueprints.learning import learning_bp
    from app.realtime import sockets  # noqa: F401

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(questions_bp)
    app.register_blueprint(exams_bp)
    app.register_blueprint(media_bp)
    app.register_blueprint(learning_bp)

    return app

