# app/models.py
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db, login_manager

exam_class_exams = db.Table(
    'exam_class_exams',
    db.Column('class_id', db.Integer, db.ForeignKey('exam_classes.id'), primary_key=True),
    db.Column('exam_id', db.Integer, db.ForeignKey('exams.id'), primary_key=True),
)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    first_name = db.Column(db.String(80), nullable=True)
    last_name = db.Column(db.String(80), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    phone = db.Column(db.String(30), nullable=True)
    institution = db.Column(db.String(150), nullable=True)
    password_hash = db.Column(db.String(255), nullable=True)
    role = db.Column(db.String(20), default='student')
    default_exam_view = db.Column(db.String(40), default='questions')

    @property
    def full_name(self):
        parts = [p for p in [self.first_name, self.last_name] if p]
        if parts:
            return " ".join(parts)
        return self.username or "Usuario"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Bank(db.Model):
    __tablename__ = 'banks'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    questions = db.relationship('Question', backref='bank', lazy=True, cascade="all, delete-orphan")

class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True)
    bank_id = db.Column(db.Integer, db.ForeignKey('banks.id'), nullable=False)
    question_type = db.Column(db.String(30), default='multiple_choice')
    statement = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), default='General')
    feedback_text = db.Column(db.Text, nullable=True)
    default_points = db.Column(db.Float, default=1.0)
    image_url = db.Column(db.String(255), nullable=True)
    video_url = db.Column(db.String(255), nullable=True)
    video_timestamp = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    options = db.relationship('QuestionOption', backref='question', cascade="all, delete-orphan")
    matching_pairs = db.relationship('QuestionMatching', backref='question', cascade="all, delete-orphan")
    order_items = db.relationship('QuestionOrder', backref='question', cascade="all, delete-orphan")

class QuestionOption(db.Model):
    __tablename__ = 'question_options'
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    option_text = db.Column(db.String(255), nullable=False)
    is_correct = db.Column(db.Boolean, default=False)

class QuestionMatching(db.Model):
    __tablename__ = 'question_matching'
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    left_text = db.Column(db.String(255), nullable=False)
    right_text = db.Column(db.String(255), nullable=False)

class QuestionOrder(db.Model):
    __tablename__ = 'question_orders'
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    item_text = db.Column(db.String(255), nullable=False)
    correct_position = db.Column(db.Integer, nullable=False)

class ExamGroup(db.Model):
    __tablename__ = 'exam_groups'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    instructor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    exams = db.relationship('Exam', backref='group', lazy=True)

class Exam(db.Model):
    __tablename__ = 'exams'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    instructions = db.Column(db.Text, nullable=True)
    duration_minutes = db.Column(db.Integer, default=30)
    passing_score = db.Column(db.Float, default=60.0)
    exam_mode = db.Column(db.String(30), default='instant_feedback')
    source_bank_id = db.Column(db.Integer, db.ForeignKey('banks.id'), nullable=True)
    random_question_count = db.Column(db.Integer, nullable=True)
    instructor_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    group_id = db.Column(db.Integer, db.ForeignKey('exam_groups.id'), nullable=True)
    status = db.Column(db.String(20), default='DRAFT')
    active = db.Column(db.Boolean, default=True)
    allow_multiple_attempts = db.Column(db.Boolean, default=False)
    max_attempts = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    source_bank = db.relationship('Bank')
    questions = db.relationship('ExamQuestion', backref='exam', cascade="all, delete-orphan", order_by="ExamQuestion.order_index")
    auto_remediation = db.Column(db.Boolean, default=False)

class ExamQuestion(db.Model):
    __tablename__ = 'exam_questions'
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id'), primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), primary_key=True)
    order_index = db.Column(db.Integer, default=1)
    points = db.Column(db.Float, default=1.0)
    question = db.relationship('Question', backref='exam_questions')

class ExamClass(db.Model):
    __tablename__ = 'exam_classes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(120), nullable=True)
    description = db.Column(db.Text, nullable=True)
    instructor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    exams = db.relationship('Exam', secondary=exam_class_exams, backref=db.backref('classes', lazy=True), lazy=True)

class ExamSession(db.Model):
    __tablename__ = 'exam_sessions'
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id'), nullable=False)
    session_code = db.Column(db.String(10), unique=True, nullable=False)
    status = db.Column(db.String(20), default='READY')
    expected_students = db.Column(db.Integer, default=0)
    question_order = db.Column(db.String(20), default='original')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    exam = db.relationship('Exam')
    attempts = db.relationship('ExamAttempt', back_populates='session', lazy=True)

class SessionQuestionSnapshot(db.Model):
    __tablename__ = 'session_question_snapshots'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('exam_sessions.id'), nullable=False)
    original_question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=True)
    order_index = db.Column(db.Integer, default=1)
    question_type = db.Column(db.String(30), default='multiple_choice')
    statement = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), default='General')
    feedback_text = db.Column(db.Text, nullable=True)
    points = db.Column(db.Float, default=1.0)
    image_url = db.Column(db.String(255), nullable=True)
    video_url = db.Column(db.String(255), nullable=True)
    video_timestamp = db.Column(db.Integer, nullable=True)
    options_data = db.Column(db.JSON, nullable=True)
    matching_data = db.Column(db.JSON, nullable=True)
    ordering_data = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    session = db.relationship('ExamSession', backref=db.backref('question_snapshots', cascade="all, delete-orphan", order_by="SessionQuestionSnapshot.order_index"))
    original_question = db.relationship('Question')

    @property
    def type_label(self):
        mapping = {
            'multiple_choice': 'Opción Múltiple',
            'single_choice': 'Opción Única',
            'multiple_select': 'Selección Múltiple',
            'true_false': 'Verdadero / Falso',
            'matching': 'Emparejamiento',
            'ordering': 'Ordenar',
            'video': 'Video',
            'short_answer': 'Respuesta Corta',
            'open_answer': 'Respuesta Abierta'
        }
        return mapping.get(self.question_type, self.question_type or 'Pregunta')

    @property
    def correct_answer_display(self):
        if self.options_data:
            corrects = [opt.get('option_text') or opt.get('text') for opt in self.options_data if opt.get('is_correct')]
            if corrects:
                return ", ".join(corrects)
        if self.matching_data:
            return "; ".join([f"{p.get('left_text')} ➔ {p.get('right_text')}" for p in self.matching_data])
        if self.ordering_data:
            sorted_items = sorted(self.ordering_data, key=lambda x: x.get('correct_position', 0))
            return " ➔ ".join([i.get('item_text') for i in sorted_items])
        return "Ver rúbrica"

class ExamAttempt(db.Model):
    __tablename__ = 'exam_attempts'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('exam_sessions.id'), nullable=False)
    attempt_number = db.Column(db.Integer, default=1)
    score = db.Column(db.Float, default=0.0)
    earned_points = db.Column(db.Float, default=0.0)
    max_points = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='completed')
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)
    student = db.relationship('User')
    session = db.relationship('ExamSession', back_populates='attempts')
    answers = db.relationship('StudentAnswer', backref='attempt', cascade="all, delete-orphan")

class StudentAnswer(db.Model):
    __tablename__ = 'student_answers'
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('exam_attempts.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    question_snapshot_id = db.Column(db.Integer, db.ForeignKey('session_question_snapshots.id'), nullable=True)
    selected_option_id = db.Column(db.Integer, db.ForeignKey('question_options.id'), nullable=True)
    question_statement = db.Column(db.Text, nullable=True)
    selected_option_text = db.Column(db.Text, nullable=True)
    correct_answer_text = db.Column(db.Text, nullable=True)
    answer_text = db.Column(db.Text, nullable=True)
    is_correct = db.Column(db.Boolean, default=False)
    points_awarded = db.Column(db.Float, default=0.0)
    question = db.relationship('Question')
    selected_option = db.relationship('QuestionOption')
    snapshot = db.relationship('SessionQuestionSnapshot', backref='student_answers')

    @property
    def display_statement(self):
        if self.question_statement:
            return self.question_statement
        if self.snapshot and self.snapshot.statement:
            return self.snapshot.statement
        if self.question and self.question.statement:
            return self.question.statement
        return "Pregunta no disponible"

    @property
    def display_student_answer(self):
        if self.selected_option_text:
            return self.selected_option_text
        if self.answer_text:
            return self.answer_text
        if self.selected_option and self.selected_option.option_text:
            return self.selected_option.option_text
        return "Sin respuesta"

    @property
    def display_correct_answer(self):
        if self.correct_answer_text:
            return self.correct_answer_text
        if self.snapshot and self.snapshot.correct_answer_display:
            return self.snapshot.correct_answer_display
        if self.question:
            if self.question.options:
                correct_opts = [opt.option_text for opt in self.question.options if opt.is_correct]
                if correct_opts:
                    return ", ".join(correct_opts)
            elif self.question.matching_pairs:
                return "; ".join([f"{p.left_text} ➔ {p.right_text}" for p in self.question.matching_pairs])
            elif self.question.order_items:
                sorted_items = sorted(self.question.order_items, key=lambda x: x.correct_position)
                return " ➔ ".join([i.item_text for i in sorted_items])
        return "Ver rúbrica"

    @property
    def display_feedback(self):
        if self.snapshot and self.snapshot.feedback_text:
            return self.snapshot.feedback_text
        if self.question and self.question.feedback_text:
            return self.question.feedback_text
        return ""

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ==========================================
# LEARNING BUILDER MODELS
# ==========================================

class Learning(db.Model):
    __tablename__ = 'learnings'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    estado = db.Column(db.String(20), default='draft')  # 'draft', 'published'
    portada = db.Column(db.String(255), nullable=True)
    autor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    # Sesión de examen que originó este curso (solo para capacitaciones de refuerzo
    # auto-generadas). Permite no duplicar el curso si la generación se dispara
    # más de una vez para la misma sesión.
    source_session_id = db.Column(db.Integer, db.ForeignKey('exam_sessions.id'), nullable=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_actualizacion = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    autor = db.relationship('User', backref='learnings')
    modules = db.relationship('LearningModule', backref='learning', cascade="all, delete-orphan", order_by="LearningModule.orden")
    progress_records = db.relationship('LearningProgress', backref='learning', cascade="all, delete-orphan")


class LearningModule(db.Model):
    __tablename__ = 'learning_modules'
    id = db.Column(db.Integer, primary_key=True)
    learning_id = db.Column(db.Integer, db.ForeignKey('learnings.id'), nullable=False)
    titulo = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    orden = db.Column(db.Integer, default=1)

    lessons = db.relationship('Lesson', backref='module', cascade="all, delete-orphan", order_by="Lesson.orden")


class Lesson(db.Model):
    __tablename__ = 'learning_lessons'
    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(db.Integer, db.ForeignKey('learning_modules.id'), nullable=False)
    titulo = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    orden = db.Column(db.Integer, default=1)

    blocks = db.relationship('Block', backref='lesson', cascade="all, delete-orphan", order_by="Block.orden")


class Block(db.Model):
    __tablename__ = 'learning_blocks'
    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey('learning_lessons.id'), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    orden = db.Column(db.Integer, default=1)
    visible = db.Column(db.Boolean, default=True)
    configuracion = db.Column(db.JSON, nullable=False, default=dict)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)

    answers = db.relationship('BlockAnswer', backref='block', cascade="all, delete-orphan")


class LearningProgress(db.Model):
    __tablename__ = 'learning_progress'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    learning_id = db.Column(db.Integer, db.ForeignKey('learnings.id'), nullable=False)
    current_lesson_id = db.Column(db.Integer, db.ForeignKey('learning_lessons.id'), nullable=True)
    current_block_id = db.Column(db.Integer, db.ForeignKey('learning_blocks.id'), nullable=True)
    progress_percent = db.Column(db.Float, default=0.0)
    time_spent_seconds = db.Column(db.Integer, default=0)
    score = db.Column(db.Float, default=0.0)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed = db.Column(db.Boolean, default=False)

    student = db.relationship('User', backref='learning_progresses')
    current_lesson = db.relationship('Lesson')
    current_block = db.relationship('Block')


class BlockAnswer(db.Model):
    __tablename__ = 'learning_block_answers'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    block_id = db.Column(db.Integer, db.ForeignKey('learning_blocks.id'), nullable=False)
    answer_data = db.Column(db.JSON, nullable=False, default=dict)
    is_correct = db.Column(db.Boolean, nullable=True)
    score = db.Column(db.Float, default=0.0)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User')


# ==========================================
# POLL / ENCUESTA EN VIVO
# ==========================================

class Poll(db.Model):
    __tablename__ = 'polls'
    id = db.Column(db.Integer, primary_key=True)
    instructor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    room_code = db.Column(db.String(20), nullable=False)
    # 'poll' = encuesta libre | 'true_false' | 'multiple_choice' | 'open_answer'
    poll_type = db.Column(db.String(30), default='poll')
    question_text = db.Column(db.Text, nullable=False)
    # JSON list of option strings, null for open_answer/poll
    options_json = db.Column(db.JSON, nullable=True)
    status = db.Column(db.String(20), default='open')   # open | closed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    instructor = db.relationship('User')
    votes = db.relationship('PollVote', backref='poll', cascade='all, delete-orphan')

    @property
    def vote_count(self):
        return len(self.votes)

    def results(self):
        """Devuelve {opcion: conteo} para opciones fijas, o lista de textos para abiertas."""
        if self.poll_type in ('open_answer', 'poll'):
            return [v.answer_text for v in self.votes if v.answer_text]
        counts = {}
        for opt in (self.options_json or []):
            counts[opt] = 0
        for v in self.votes:
            key = v.answer_text
            if key in counts:
                counts[key] += 1
        return counts


# ==========================================
# RESPUESTAS EN VIVO (progreso sin snapshot)
# ==========================================

class LiveAnswer(db.Model):
    """
    Guarda la última respuesta enviada por cada estudiante para cada pregunta
    durante una sesión en vivo. No depende de que el snapshot esté completo.
    Se usa para restaurar progreso si el examen se pausa o el estudiante
    recarga la página. ON CONFLICT = reemplazar (upsert por student+session+question).
    """
    __tablename__ = 'live_answers'
    id = db.Column(db.Integer, primary_key=True)
    session_id  = db.Column(db.Integer, db.ForeignKey('exam_sessions.id'), nullable=False)
    student_id  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    question_id = db.Column(db.Integer, nullable=False)  # ID lógico (no FK estricta)
    # Serialización JSON de la respuesta: {selected_option_id, order_map, pair_map, text, ...}
    answer_json = db.Column(db.JSON, nullable=True)
    answered_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('session_id', 'student_id', 'question_id', name='uq_live_answer'),
    )


class PollVote(db.Model):
    __tablename__ = 'poll_votes'
    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey('polls.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    answer_text = db.Column(db.Text, nullable=True)
    voted_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship('User')

    __table_args__ = (
        db.UniqueConstraint('poll_id', 'student_id', name='uq_poll_student'),
    )

