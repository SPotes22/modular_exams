"""
Sockets para Polls.
Nota: NO usa csrf_token. La sesión es flask-session (cookie httponly).
Un mismo navegador puede estar en múltiples salas simultáneamente porque
cada sala usa un room_code distinto como room key de SocketIO.
"""
from flask import request
from flask_login import current_user
from flask_socketio import join_room, emit
from app.extensions import socketio


@socketio.on('poll_join_room')
def handle_poll_join(data):
    """
    Estudiante o instructor se une a la sala de poll.
    data = { room_code: str }
    """
    room_code = (data.get('room_code') or '').strip().upper()
    if not room_code:
        emit('poll_error', {'message': 'room_code requerido'})
        return
    join_room(f'room_{room_code}')
    emit('poll_room_joined', {'room_code': room_code})
