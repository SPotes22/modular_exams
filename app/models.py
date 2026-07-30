# app/models.py
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db, login_manager

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=True)
    role = db.Column(db.String(20), default='student')

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
    
    image_url = db.Column(db.String(255), nullable=True)
    video_url = db.Column(db.String(255), nullable=True)
    video_timestamp = db.Column(db.Integer, nullable=True)
    
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


class Exam(db.Model):
    __tablename__ = 'exams'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    duration_minutes = db.Column(db.Integer, default=30)
    passing_score = db.Column(db.Float, default=60.0)
    exam_mode = db.Column(db.String(30), default='instant_feedback')
    source_bank_id = db.Column(db.Integer, db.ForeignKey('banks.id'), nullable=True)
    random_question_count = db.Column(db.Integer, nullable=True)
    instructor_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    source_bank = db.relationship('Bank')
    questions = db.relationship('ExamQuestion', backref='exam', cascade="all, delete-orphan")


class ExamQuestion(db.Model):
    __tablename__ = 'exam_questions'
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id'), primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), primary_key=True)
    points = db.Column(db.Float, default=1.0)
    question = db.relationship('Question', backref='exam_questions')


class ExamSession(db.Model):
    __tablename__ = 'exam_sessions'
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id'), nullable=False)
    session_code = db.Column(db.String(10), unique=True, nullable=False)
    status = db.Column(db.String(20), default='waiting')
    expected_students = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    exam = db.relationship('Exam')
    attempts = db.relationship('ExamAttempt', back_populates='session', lazy=True)


class ExamAttempt(db.Model):
    __tablename__ = 'exam_attempts'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('exam_sessions.id'), nullable=False)
    score = db.Column(db.Float, default=0.0)
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
    selected_option_id = db.Column(db.Integer, db.ForeignKey('question_options.id'), nullable=True)
    is_correct = db.Column(db.Boolean, default=False)
    question = db.relationship('Question')
    selected_option = db.relationship('QuestionOption')


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
