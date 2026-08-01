from flask import request
from flask_login import current_user
from flask_socketio import emit
from app.extensions import socketio, db
from app.models import ExamSession
from app.realtime.manager import session_manager


@socketio.on('teacher_start_exam')
def handle_teacher_start_exam(data):
    """
    Inicia formalmente la sesión de examen para todos los alumnos en la sala.
    data = { 'session_code': 'AFLMD9' }
    """
    session_code = data.get('session_code', '').strip().upper()
    rt_session = session_manager.get_session_by_code(session_code)

    if not rt_session:
        emit('error', {'message': 'Sesión no encontrada en RAM.'})
        return

    # Actualizar estado en RAM y Base de Datos
    rt_session.status = 'in_progress'
    session_obj = ExamSession.query.get(rt_session.session_id)
    if session_obj:
        session_obj.status = 'in_progress'
        db.session.commit()

    room_name = f"session_{session_code}"
    
    # Transmisión global a la sala para desbloquear la pantalla a los estudiantes
    emit('exam_started', {
        'session_code': session_code,
        'status': 'in_progress'
    }, to=room_name)


@socketio.on('teacher_next_question')
def handle_teacher_next_question(data):
    """
    Avanza a la siguiente pregunta global en la modalidad Teacher Paced.
    data = { 'session_code': 'AFLMD9' }
    """
    session_code = data.get('session_code', '').strip().upper()
    rt_session = session_manager.get_session_by_code(session_code)

    if not rt_session:
        emit('error', {'message': 'Sesión no encontrada.'})
        return

    instructor_id = current_user.id if hasattr(current_user, 'id') else data.get('instructor_id')

    # Invocar el método next_question de la estrategia activa
    success, payload = rt_session.mode_strategy.next_question(instructor_id=instructor_id)

    if not success:
        emit('action_rejected', payload)
        return

    room_name = f"session_{session_code}"

    if payload.get('action') == 'question_changed':
        # Transmitir la nueva pregunta a todos los alumnos
        emit('question_advanced', payload, to=room_name)
    elif payload.get('action') == 'exam_completed':
        # Notificar que se terminaron todas las preguntas
        emit('all_questions_presented', payload, to=room_name)


@socketio.on('teacher_close_exam')
def handle_teacher_close_exam(data):
    """
    Cierra la sesión de examen globalmente y desaloja la sala.
    data = { 'session_code': 'AFLMD9' }
    """
    session_code = data.get('session_code', '').strip().upper()
    rt_session = session_manager.get_session_by_code(session_code)

    if not rt_session:
        emit('error', {'message': 'Sesión no encontrada.'})
        return

    instructor_id = current_user.id if hasattr(current_user, 'id') else data.get('instructor_id')

    # Ejecutar cierre en la modalidad activa
    payload = rt_session.mode_strategy.finish(user_id=instructor_id, is_instructor=True)

    # Actualizar estado en la BD y liberar de la memoria RAM
    session_obj = ExamSession.query.get(rt_session.session_id)
    if session_obj:
        session_obj.status = 'finished'
        db.session.commit()

    room_name = f"session_{session_code}"
    
    # Emitir evento de cierre a todos los participantes
    emit('exam_closed_by_teacher', payload, to=room_name)

    # Remover la sesión de la memoria RAM
    session_manager.close_session(rt_session.session_id)
