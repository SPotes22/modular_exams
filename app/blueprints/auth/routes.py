from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models import User, ExamSession
from app.blueprints.auth import auth_bp

@auth_bp.route('/')
def home():
    if current_user.is_authenticated:
        if current_user.role == 'instructor':
            return redirect(url_for('exams.instructor_dashboard'))
        return redirect(url_for('auth.student_join_exam'))
    return render_template('login.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email, role='instructor').first()
        
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('exams.instructor_dashboard'))
        
        flash('Credenciales de profesor inválidas', 'danger')
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.home'))

@auth_bp.route('/student/join', methods=['GET', 'POST'])
def student_join_exam():
    if request.method == 'POST':
        student_name = request.form.get('student_name', '').strip()
        code = request.form.get('session_code', '').strip().upper()
        
        # Buscar la sesión activa en la BD
        exam_session = ExamSession.query.filter_by(
            session_code=code, 
            status='waiting' # O status != 'closed'
        ).first()

        if not student_name or not code:
            flash('Debes ingresar tu nombre y un código de examen válido.', 'warning')
            return redirect(url_for('auth.student_join_exam'))

        session_obj = ExamSession.query.filter_by(session_code=code).first()
        if not session_obj:
            flash('Código de examen no encontrado.', 'danger')
            return redirect(url_for('auth.student_join_exam'))

        if session_obj.status == 'finished':
            flash('Esta sala ya finalizó.', 'danger')
            return redirect(url_for('auth.student_join_exam'))

        user = User(username=student_name, role='student')
        db.session.add(user)
        db.session.commit()
        login_user(user)

        return redirect(url_for('exams.presentar_examen', session_id=exam_session.id))

    return render_template('student_join.html')
