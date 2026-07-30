from flask import request
from flask_socketio import emit, join_room
from app.extensions import db, socketio
from app.models import ExamSession

@socketio.on('join_session_room')
def handle_join_session_room(data):
    session_code = str(data.get('session_code', '')).strip().upper()
    username = data.get('username', 'Estudiante')
    room = f"session_{session_code}"
    
    # 1. Unir socket actual a la sala
    join_room(room)
    print(f"--> [SOCKET] {username} (SID: {request.sid}) se unió a la sala: {room}")
    
    # 2. Avisar al instructor (Lobby) que alguien entró
    emit('user_joined', {
        'username': username, 
        'msg': f'{username} se ha unido.'
    }, to=room)

    # 3. Si la sesión YA estaba en curso cuando entró/recargó, desbloquear pantalla ya mismo
    session_obj = ExamSession.query.filter_by(session_code=session_code).first()
    if session_obj and session_obj.status == 'in_progress':
        print(f"--> [SOCKET] La sesión {session_code} ya está activa. Notificando a {username}")
        emit('exam_started', {'status': 'in_progress'}, room=request.sid)


@socketio.on('start_exam_session')
def handle_start_exam_session(data):
    session_id = data.get('session_id')
    session_obj = ExamSession.query.get(session_id)
    
    if session_obj:
        session_obj.status = 'in_progress'
        db.session.commit()
        
        room = f"session_{session_obj.session_code}"
        print(f"--> [SOCKET] INSTRUCTOR inició la sesión ID {session_id}. Difundiendo a sala: {room}")
        
        # OJO: Se emite a toda la sala (Lobby e Instructores y Estudiantes)
        socketio.emit('exam_started', {'status': 'in_progress'}, to=room)

# NUEVO: Evento para registrar las alertas Anti-Cheat enviadas por los estudiantes
@socketio.on('anti_cheat_alert')
def handle_anti_cheat_alert(data):
    session_code = data.get('session_code')
    username = data.get('username')
    reason = data.get('reason')
    room = f"session_{session_code}"

    # Emitir la alerta únicamente al panel del instructor dentro de la misma sala
    emit('cheat_warning', {
        'username': username,
        'reason': reason
    }, to=room)
