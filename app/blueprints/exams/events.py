from flask_socketio import join_room, leave_room, emit
from flask import request
# importa tu instancia de socketio (ej: from app import socketio)

@socketio.on('student_join_room')
def handle_student_join(data):
    session_code = data.get('session_code')
    if not session_code:
        return
    
    # 1. Unir el socket a la sala del código de examen
    join_room(session_code)
    
    # 2. Notificar al profesor (y a la sala) que un estudiante se unió
    # Usa el usuario actual de Flask-Login
    from flask_login import current_user
    username = current_user.username if current_user.is_authenticated else "Estudiante"
    student_id = current_user.id if current_user.is_authenticated else request.sid

    emit('student_joined', {
        'student_id': student_id,
        'username': username
    }, to=session_code)

@socketio.on('teacher_join_room')
def handle_teacher_join(data):
    session_code = data.get('session_code')
    if session_code:
        join_room(session_code)

@socketio.on('teacher_start_exam')
def handle_start_exam(data):
    session_code = data.get('session_code')
    if session_code:
        # Emitir a TODOS en la sala (incluyendo estudiantes) que la prueba inició
        emit('exam_started', {'status': 'in_progress'}, to=session_code)
