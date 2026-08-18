from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models import User, ExamSession
from app.blueprints.auth import auth_bp

@auth_bp.route('/')
def home():
    if current_user.is_authenticated:
        if current_user.role in ['superuser', 'admin']:
            return redirect(url_for('admin.dashboard'))
        elif current_user.role == 'instructor':
            view = getattr(current_user, 'default_exam_view', 'questions')
            endpoint = {'questions': 'questions.mis_preguntas', 'exams': 'exams.library', 'classes': 'exams.classes', 'learning': 'learning.instructor_dashboard'}.get(view, 'exams.instructor_dashboard')
            return redirect(url_for(endpoint))
        return redirect(url_for('auth.student_join_exam'))
    return render_template('login.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user)
            if user.role in ['superuser', 'admin']:
                flash(f'Bienvenido Superusuario {user.username}', 'success')
                return redirect(url_for('admin.dashboard'))
            elif user.role == 'instructor':
                flash(f'Bienvenido Profesor {user.username}', 'success')
                view = getattr(user, 'default_exam_view', 'questions')
                endpoint = {'questions': 'questions.mis_preguntas', 'exams': 'exams.library', 'classes': 'exams.classes', 'learning': 'learning.instructor_dashboard'}.get(view, 'exams.instructor_dashboard')
                return redirect(url_for(endpoint))
            else:
                flash('Los estudiantes deben ingresar con su código de sala.', 'info')
                return redirect(url_for('auth.student_join_exam'))
        
        flash('Credenciales de acceso inválidas', 'danger')
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

        return redirect(url_for('exams.presentar_examen', session_id=session_obj.id))

    return render_template('student_join.html')
