import string
import random
from flask import Blueprint, flash, redirect, render_template, request, url_for, send_file
from flask_login import current_user, login_required
from app.exams.services import ExamService
from app.models import Exam, ExamSession, Question
from app.student.services import StudentService
from app.realtime.manager import session_manager

exams_bp = Blueprint('exams', __name__)


def generate_session_code(length=6):
    """Genera un código alfanumérico aleatorio único para la sesión."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))


@exams_bp.route('/instructor/dashboard')
@login_required
def instructor_dashboard():
    """Muestra la lista de exámenes creados por el instructor actual."""
    if getattr(current_user, 'role', '') != 'instructor':
        flash('Acceso denegado. Se requieren permisos de instructor.', 'danger')
        return redirect(url_for('student.join_exam'))

    exams = Exam.query.filter_by(instructor_id=current_user.id).all()
    return render_template('instructor_dashboard.html', exams=exams)


@exams_bp.route('/instructor/session/create/<int:exam_id>', methods=['POST'])
@login_required
def create_session(exam_id):
    """Genera una nueva sesión activa para un examen y redirige al lobby."""
    exam = Exam.query.get_or_404(exam_id)
    session_code = generate_session_code()
    
    session_obj = ExamService.create_session(exam_id=exam.id, session_code=session_code)
    
    # Preparar e inicializar la sesión en RAM a través del StudentService
    StudentService.get_and_prepare_session(session_code)

    return redirect(url_for('exams.instructor_lobby', session_id=session_obj.id))


@exams_bp.route('/instructor/lobby/<int:session_id>')
@login_required
def instructor_lobby(session_id):
    """Carga la interfaz de control en vivo para el profesor (instructor_lobby.html)."""
    session_obj = ExamSession.query.get_or_404(session_id)
    rt_session = session_manager.get_session_by_id(session_id)

    if not rt_session:
        StudentService.get_and_prepare_session(session_obj.session_code)
        rt_session = session_manager.get_session_by_id(session_id)

    return render_template(
        'instructor_lobby.html',
        session_id=session_obj.id,
        session_code=session_obj.session_code,
        exam_title=session_obj.exam.title,
        exam_mode=session_obj.exam.exam_mode,
        session_status=session_obj.status
    )


@exams_bp.route('/instructor/session/report/<int:session_id>')
@login_required
def session_report(session_id):
    """Muestra el reporte detallado de resultados de una sesión."""
    session_obj = ExamSession.query.get_or_404(session_id)
    return render_template('session_report.html', session=session_obj)


@exams_bp.route('/instructor/session/export/<int:session_id>')
@login_required
def export_session_excel(session_id):
    """Genera y descarga el archivo Excel con los resultados de la prueba."""
    session_obj = ExamSession.query.get_or_404(session_id)
    excel_stream = ExamService.generate_excel_report(session_id)
    
    filename = f"Reporte_Examen_{session_obj.session_code}.xlsx"
    return send_file(
        excel_stream,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )
