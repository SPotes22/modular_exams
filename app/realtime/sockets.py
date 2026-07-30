from flask import request
from flask_login import current_user
from flask_socketio import emit, join_room
from app.extensions import db, socketio
from app.models import ExamSession as DbExamSession
from app.modes import registry
from app.realtime import events
from app.realtime.manager import session_manager
from app.services.exam_content import normalize_room_code, socket_room


def _mode(session):
    return registry.get(session.mode, socketio, session_manager)


def _emit_students(session):
    payload = {'students': session_manager.students_payload(session), 'room_code': session.room_code}
    socketio.emit(events.STUDENTS_UPDATED, payload, to=session.teacher_sid or socket_room(session.room_code))
    print(f"[ROOM] Estudiantes conectados: {len([s for s in session.students.values() if s.connected])}")


@socketio.on(events.TEACHER_JOIN)
def handle_teacher_join(data):
    room_code = normalize_room_code(data.get('room_code'))
    session = session_manager.set_teacher(room_code, request.sid)
    if not session:
        emit(events.ERROR, {'message': 'Sesión no encontrada'})
        return
    join_room(socket_room(room_code))
    print(f"[JOIN] Profesor -> {room_code}")
    _emit_students(session)


@socketio.on(events.STUDENT_JOIN)
@socketio.on(events.JOIN_SESSION_ROOM)
def handle_student_join(data):
    room_code = normalize_room_code(data.get('room_code') or data.get('session_code'))
    student_id = data.get('student_id') or (current_user.id if current_user.is_authenticated else None)
    username = data.get('username') or (current_user.username if current_user.is_authenticated else 'Estudiante')
    if not student_id:
        emit(events.ERROR, {'message': 'Estudiante no autenticado'})
        return
    result = session_manager.add_student(room_code, student_id, username, request.sid)
    if not result:
        emit(events.ERROR, {'message': 'Sesión no encontrada'})
        return
    session, student = result
    join_room(socket_room(room_code))
    print(f"[JOIN] Alumno {student.id} -> {room_code}")
    _emit_students(session)
    _mode(session).on_join(session, student)


@socketio.on(events.START_EXAM_SESSION)
def handle_start_exam_session(data):
    session_id = data.get('session_id')
    db_session = DbExamSession.query.get(session_id)
    if not db_session:
        emit(events.ERROR, {'message': 'Sesión no encontrada'})
        return
    db_session.status = 'in_progress'
    db.session.commit()
    session = session_manager.get_or_create_by_db_session(db_session)
    session.status = 'in_progress'
    print(f"[START] Profesor inició {session.room_code}")
    _mode(session).on_start(session)


@socketio.on(events.ANSWER_SUBMITTED)
def handle_answer_submitted(data):
    room_code = normalize_room_code(data.get('room_code'))
    session = session_manager.get_or_create_by_code(room_code)
    student_id = data.get('student_id') or (current_user.id if current_user.is_authenticated else None)
    question_id = int(data.get('question_id') or 0)
    if not session or session.status != 'in_progress' or session.status == 'finished':
        emit(events.ERROR, {'message': 'Examen no disponible'})
        return
    student = session.students.get(int(student_id)) if student_id else None
    if not student or student.sid != request.sid or question_id not in [q['id'] for q in session.questions]:
        emit(events.ERROR, {'message': 'Respuesta rechazada'})
        return
    _mode(session).on_answer(session, student, question_id, data.get('answer') or {})


@socketio.on(events.NEXT_QUESTION)
def handle_next_question(data):
    room_code = normalize_room_code(data.get('room_code'))
    session = session_manager.get_or_create_by_code(room_code)
    if not session or session.teacher_sid != request.sid:
        emit(events.ERROR, {'message': 'Profesor no autorizado'})
        return
    _mode(session).on_next_question(session)


@socketio.on(events.ANTI_CHEAT_ALERT)
def handle_anti_cheat_alert(data):
    room_code = normalize_room_code(data.get('room_code') or data.get('session_code'))
    print(f"[ALERT] {data.get('username')} -> {room_code}: {data.get('reason')}")
    emit(events.CHEAT_WARNING, {'username': data.get('username'), 'reason': data.get('reason')}, to=socket_room(room_code))


@socketio.on('disconnect')
def handle_disconnect():
    info = session_manager.disconnect_sid(request.sid)
    if not info:
        return
    session, role, student_id = info
    if role == 'student':
        print(f"[LEAVE] Alumno {student_id} <- {session.room_code}")
        _emit_students(session)
    else:
        print(f"[LEAVE] Profesor <- {session.room_code}")
