from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app.student.services import StudentService
from app.realtime.manager import session_manager

student_bp = Blueprint('student', __name__)


@student_bp.route('/student/join', methods=['GET', 'POST'])
@login_required
def join_exam():
    """Vista para que el estudiante ingrese el código de sesión de 6 caracteres."""
    if request.method == 'POST':
        session_code = request.form.get('session_code', '').strip().upper()
        if not session_code:
            flash('Por favor ingresa un código válido.', 'warning')
            return redirect(url_for('student.join_exam'))

        session_obj = StudentService.get_and_prepare_session(session_code)
        if not session_obj:
            flash('La sala de examen no existe.', 'danger')
            return redirect(url_for('student.join_exam'))

        if session_obj.status == 'finished':
            flash('Esta sesión de examen ya ha sido finalizada.', 'info')
            return redirect(url_for('student.join_exam'))

        return redirect(url_for('student.presentar_examen', session_id=session_obj.id))

    return render_template('student_join.html')


@student_bp.route('/exam/presentar/<int:session_id>')
@login_required
def presentar_examen(session_id):
    """Carga el entorno de prueba para el estudiante (presentar_examen.html)."""
    rt_session = session_manager.get_session_by_id(session_id)
    
    if not rt_session:
        # Intenta reconstruir la sesión en memoria si proviene de un enlace directo
        from app.models import ExamSession
        session_obj = ExamSession.query.get_or_404(session_id)
        StudentService.get_and_prepare_session(session_obj.session_code)
        rt_session = session_manager.get_session_by_id(session_id)

    if not rt_session:
        flash('No se pudo cargar la sesión del examen.', 'danger')
        return redirect(url_for('student.join_exam'))

    return render_template(
        'presentar_examen.html',
        session_id=rt_session.session_id,
        session_code=rt_session.session_code,
        exam_mode=rt_session.mode_name,
        session_status=rt_session.status
    )
