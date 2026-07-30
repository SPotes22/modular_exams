from abc import ABC, abstractmethod


class ExamMode(ABC):
    name = None

    def __init__(self, socketio, manager):
        self.socketio = socketio
        self.manager = manager

    @abstractmethod
    def on_join(self, session, student): ...

    @abstractmethod
    def on_start(self, session): ...

    @abstractmethod
    def on_answer(self, session, student, question_id, answer): ...

    @abstractmethod
    def on_next_question(self, session): ...

    @abstractmethod
    def finish(self, session, student=None): ...
