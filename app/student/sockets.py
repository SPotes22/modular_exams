from flask import request
from flask_login import current_user
from flask_socketio import emit
from app.extensions import socketio
from app.realtime.manager import session_manager
from app.student.services import StudentService


@socketio.on('submit_answer')
def handle_submit_answer(data):
    """
    Maneja la recepción de una respuesta de un estudiante en tiempo real.
    data = { 'session_code': 'AFLMD9', 'question_id': 12, 'answer_data': { 'option_id': 3 } }
    """
    session_code = data.get('session_code', '').strip().upper()
    question_id = data.get('question_id')
    answer_data = data.get('answer_data', {})

    rt_session = session_manager.get_session_by_code(session_code)
    if not rt_session:
        emit('error', {'message': 'Sesión no encontrada en memoria RAM.'})
        return

    student_id = current_user.id if hasattr(current_user, 'id') else data.get('student_id')

    # Ejecuta el método on_answer de la modalidad configurada (Open Nav, Instant, Teacher Paced)
    success, payload = rt_session.mode_strategy.on_answer(
        student_id=student_id,
        question_id=question_id,
        answer_data=answer_data
    )

    if not success:
        emit('answer_rejected', payload)
        return

    # Emite la confirmación/feedback directo al estudiante que respondió
    emit('answer_processed', payload)

    # Si la modalidad indica que la pregunta la respondieron todos, se notifica a la sala del profesor
    if payload.get('all_answered'):
        room_name = f"session_{session_code}"
        emit('teacher_can_continue', {
            'question_id': question_id,
            'message': 'Todos los estudiantes conectados han respondido esta pregunta.'
        }, to=room_name)


@socketio.on('finish_exam')
def handle_finish_exam(data):
    """
    Procesa la finalización voluntaria o automática del examen de un estudiante.
    data = { 'session_code': 'AFLMD9' }
    """
    session_code = data.get('session_code', '').strip().upper()
    rt_session = session_manager.get_session_by_code(session_code)

    if not rt_session:
        emit('error', {'message': 'Sesión no activa.'})
        return

    student_id = current_user.id if hasattr(current_user, 'id') else data.get('student_id')

    # Notificar a la estrategia de modalidad
    result = rt_session.mode_strategy.finish(user_id=student_id, is_instructor=False)

    # Recuperar las respuestas guardadas en RAM y escribirlas en la Base de Datos
    student_answers = rt_session.get_student_answers(student_id)
    attempt = StudentService.save_final_attempt(
        student_id=student_id,
        session_id=rt_session.session_id,
        answers_dict=student_answers
    )

    room_name = f"session_{session_code}"

    # Avisar al profesor que un alumno terminó
    emit('student_finished_exam', {
        'student_id': student_id,
        'username': current_user.username if hasattr(current_user, 'username') else 'Estudiante',
        'attempt_id': attempt.id
    }, to=room_name)

    # Confirmarle al alumno que su examen fue guardado con éxito y enviarle la URL de sus resultados
    emit('exam_submitted_success', {
        'attempt_id': attempt.id,
        'redirect_url': f"/resultados/{attempt.id}"
    })
