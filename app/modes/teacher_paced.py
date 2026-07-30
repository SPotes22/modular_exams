from app.modes.base import ExamMode
from app.modes.registry import registry
from app.realtime import events
from app.services.exam_content import grade_answer, socket_room


@registry.register
class TeacherPacedMode(ExamMode):
    name = 'teacher_paced'

    def _current(self, session):
        return session.questions[session.current_question] if session.current_question < len(session.questions) else None

    def on_join(self, session, student):
        student.current_question = session.current_question
        self.socketio.emit(events.SESSION_STATE, {'mode': self.name, 'status': session.status, 'question': self._current(session), 'current_question': session.current_question}, to=student.sid)

    def on_start(self, session):
        self.socketio.emit(events.EXAM_STARTED, {'status': session.status, 'mode': self.name, 'question': self._current(session)}, to=socket_room(session.room_code))

    def on_answer(self, session, student, question_id, answer):
        current = self._current(session)
        if not current or question_id != current['id']:
            self.socketio.emit(events.ERROR, {'message': 'Pregunta no habilitada por el profesor.'}, to=student.sid)
            return
        result = grade_answer(current, answer)
        student.answered_questions[question_id] = {'answer': answer, 'result': result}
        student.score += result['points']
        print(f"[ANSWER] {student.id} respondió {question_id}")
        if session.students and all(current['id'] in s.answered_questions for s in session.students.values()):
            self.socketio.emit(events.TEACHER_CAN_CONTINUE, {'question': session.current_question}, to=session.teacher_sid)

    def on_next_question(self, session):
        session.current_question += 1
        print(f"[NEXT] Profesor avanzó a pregunta {session.current_question}")
        self.socketio.emit(events.NEXT_QUESTION, {'question': self._current(session), 'current_question': session.current_question}, to=socket_room(session.room_code))

    def finish(self, session, student=None):
        session.status = 'finished'
        self.socketio.emit(events.EXAM_FINISHED, {}, to=socket_room(session.room_code))
