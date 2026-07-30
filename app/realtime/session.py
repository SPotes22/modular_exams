from dataclasses import dataclass, field


@dataclass
class StudentSession:
    id: int
    username: str
    sid: str | None = None
    answered_questions: dict = field(default_factory=dict)
    current_question: int = 0
    score: float = 0.0
    connected: bool = True


@dataclass
class ExamSession:
    room_code: str
    session_id: int
    exam_id: int
    teacher_sid: str | None = None
    students: dict = field(default_factory=dict)
    questions: list = field(default_factory=list)
    current_question: int = 0
    status: str = 'waiting'
    mode: str = 'instant_feedback'
