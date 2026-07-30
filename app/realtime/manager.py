from app.models import ExamSession as DbExamSession
from app.realtime.session import ExamSession, StudentSession
from app.services.exam_content import load_session_questions, normalize_room_code


class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.sid_index = {}

    def get_or_create_by_db_session(self, db_session):
        room_code = normalize_room_code(db_session.session_code)
        session = self.sessions.get(room_code)
        if not session:
            session = ExamSession(
                room_code=room_code,
                session_id=db_session.id,
                exam_id=db_session.exam_id,
                questions=load_session_questions(db_session.id),
                status=db_session.status,
                mode=db_session.exam.exam_mode or 'instant_feedback',
            )
            self.sessions[room_code] = session
        else:
            session.status = db_session.status
        return session

    def get_or_create_by_code(self, room_code):
        room_code = normalize_room_code(room_code)
        session = self.sessions.get(room_code)
        if session:
            return session
        db_session = DbExamSession.query.filter_by(session_code=room_code).first()
        return self.get_or_create_by_db_session(db_session) if db_session else None

    def set_teacher(self, room_code, sid):
        session = self.get_or_create_by_code(room_code)
        if not session:
            return None
        session.teacher_sid = sid
        self.sid_index[sid] = (session.room_code, 'teacher', None)
        return session

    def add_student(self, room_code, student_id, username, sid):
        session = self.get_or_create_by_code(room_code)
        if not session:
            return None
        student_id = int(student_id)
        student = session.students.get(student_id)
        if not student:
            student = StudentSession(id=student_id, username=username, sid=sid)
            session.students[student_id] = student
        else:
            student.sid = sid
            student.username = username or student.username
            student.connected = True
        self.sid_index[sid] = (session.room_code, 'student', student_id)
        return session, student

    def disconnect_sid(self, sid):
        info = self.sid_index.pop(sid, None)
        if not info:
            return None
        room_code, role, student_id = info
        session = self.sessions.get(room_code)
        if not session:
            return None
        if role == 'teacher' and session.teacher_sid == sid:
            session.teacher_sid = None
        if role == 'student' and student_id in session.students:
            session.students[student_id].connected = False
            session.students[student_id].sid = None
        return session, role, student_id

    def students_payload(self, session):
        return [{
            'id': s.id,
            'username': s.username,
            'connected': s.connected,
            'answered_count': len(s.answered_questions),
            'score': s.score,
        } for s in session.students.values()]

    def start(self, room_code):
        session = self.get_or_create_by_code(room_code)
        if session:
            session.status = 'in_progress'
        return session


session_manager = SessionManager()
