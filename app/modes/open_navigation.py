from app.modes.base import ExamMode
from app.modes.registry import registry
from app.realtime import events
from app.services.exam_content import grade_answer, socket_room


@registry.register
class OpenNavigationMode(ExamMode):
    name = 'open_navigation'

    def on_join(self, session, student):
        self.socketio.emit(events.SESSION_STATE, {'mode': self.name, 'status': session.status, 'questions': session.questions, 'answers': student.answered_questions}, to=student.sid)

    def on_start(self, session):
        self.socketio.emit(events.EXAM_STARTED, {'status': session.status, 'mode': self.name, 'questions': session.questions}, to=socket_room(session.room_code))

    def on_answer(self, session, student, question_id, answer):
        question = next((q for q in session.questions if q['id'] == question_id), None)
        result = grade_answer(question, answer)
        student.answered_questions[question_id] = {'answer': answer, 'result': result}
        can_submit = len(student.answered_questions) == len(session.questions)
        print(f"[ANSWER] {student.id} respondió {question_id}")
        self.socketio.emit(events.SESSION_STATE, {'answered': list(student.answered_questions), 'can_submit': can_submit}, to=student.sid)

    def on_next_question(self, session):
        return None

    def finish(self, session, student=None):
        if student:
            self.socketio.emit(events.EXAM_FINISHED, {'student_id': student.id}, to=student.sid)
