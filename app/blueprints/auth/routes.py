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
        return redirect(url_for('learning.student_catalog'))
    return render_template('login.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated and request.method == 'GET':
        return redirect(url_for('auth.home'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user)
            display_name = user.first_name or user.username
            if user.role in ['superuser', 'admin']:
                flash(f'Bienvenido Superusuario {display_name}', 'success')
                return redirect(url_for('admin.dashboard'))
            elif user.role == 'instructor':
                flash(f'Bienvenido Profesor {display_name}', 'success')
                view = getattr(user, 'default_exam_view', 'questions')
                endpoint = {'questions': 'questions.mis_preguntas', 'exams': 'exams.library', 'classes': 'exams.classes', 'learning': 'learning.instructor_dashboard'}.get(view, 'exams.instructor_dashboard')
                return redirect(url_for(endpoint))
            else:
                flash(f'Bienvenido(a) {display_name}', 'success')
                return redirect(url_for('learning.student_catalog'))
        
        flash('Credenciales de acceso inválidas', 'danger')
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
@auth_bp.route('/registro', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated and request.method == 'GET':
        return redirect(url_for('auth.home'))

    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        password_confirm = request.form.get('password_confirm', '').strip()
        phone = request.form.get('phone', '').strip()
        role_raw = request.form.get('role', 'student').strip().lower()
        institution = request.form.get('institution', '').strip()

        # Validaciones de campos obligatorios
        if not first_name or not last_name or not email or not password:
            flash('Por favor completa todos los campos requeridos: Nombre, Apellido, Correo y Contraseña.', 'warning')
            return render_template('register.html', form_data=request.form)

        if '@' not in email or '.' not in email:
            flash('Por favor ingresa un correo electrónico válido.', 'warning')
            return render_template('register.html', form_data=request.form)

        if len(password) < 4:
            flash('La contraseña debe tener al menos 4 caracteres.', 'warning')
            return render_template('register.html', form_data=request.form)

        if password_confirm and password != password_confirm:
            flash('Las contraseñas no coinciden.', 'warning')
            return render_template('register.html', form_data=request.form)

        # Determinar rol (estudiante o profesor/instructor)
        role = 'instructor' if role_raw in ['instructor', 'profesor', 'teacher', 'docente'] else 'student'

        # Verificar unicidad de correo
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash(f'Ya existe una cuenta registrada con el correo "{email}".', 'danger')
            return render_template('register.html', form_data=request.form)

        full_name = f"{first_name} {last_name}".strip()
        new_user = User(
            username=full_name,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            institution=institution,
            role=role,
            default_exam_view='questions' if role == 'instructor' else 'catalog'
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        display_name = new_user.first_name or new_user.username
        role_label = 'Profesor' if new_user.role == 'instructor' else 'Estudiante'
        flash(f'¡Cuenta creada exitosamente! Bienvenido(a) {role_label} {display_name}.', 'success')

        if new_user.role == 'instructor':
            return redirect(url_for('exams.instructor_dashboard'))
        return redirect(url_for('learning.student_catalog'))

    return render_template('register.html', form_data={})

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
