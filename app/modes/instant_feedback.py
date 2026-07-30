from app.modes.base import ExamMode
from app.modes.registry import registry
from app.realtime import events
from app.services.exam_content import grade_answer, socket_room


@registry.register
class InstantFeedbackMode(ExamMode):
    name = 'instant_feedback'

    def on_join(self, session, student):
        index = min(student.current_question, max(len(session.questions) - 1, 0))
        question = session.questions[index] if session.questions else None
        self.socketio.emit(events.SESSION_STATE, {'mode': self.name, 'status': session.status, 'question': question, 'current_question': index}, to=student.sid)

    def on_start(self, session):
        first = session.questions[0] if session.questions else None
        self.socketio.emit(events.EXAM_STARTED, {'status': session.status, 'mode': self.name, 'question': first}, to=socket_room(session.room_code))

    def on_answer(self, session, student, question_id, answer):
        question = next((q for q in session.questions if q['id'] == question_id), None)
        result = grade_answer(question, answer)
        student.answered_questions[question_id] = {'answer': answer, 'result': result}
        student.score += result['points']
        student.current_question = min(student.current_question + 1, len(session.questions))
        next_question = session.questions[student.current_question] if student.current_question < len(session.questions) else None
        print(f"[ANSWER] {student.id} respondió {question_id}")
        self.socketio.emit(events.FEEDBACK, {**result, 'next_question': next_question, 'finished': next_question is None}, to=student.sid)

    def on_next_question(self, session):
        return None

    def finish(self, session, student=None):
        target = student.sid if student else socket_room(session.room_code)
        self.socketio.emit(events.EXAM_FINISHED, {}, to=target)
