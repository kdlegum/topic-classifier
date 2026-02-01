from sqlmodel import Field, Session, SQLModel, create_engine
import uuid
from datetime import datetime
from enum import Enum

"""
Session (exam paper, model = X)
  └── Question
        ├── Prediction (rank 1)
        ├── Prediction (rank 2)
        └── Prediction (rank 3)
"""

class QuestionStatus(str, Enum):
    not_marked = "not_marked"
    mak = "marked"

class SessionStatus(str, Enum):
    not_marked = "not_marked"
    in_progress = "in_progress"
    marked = "marked"

class Session(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()), index=True, unique=True)
    user_id: str | None
    is_guest: bool = Field(default=True)
    exam_board: str
    subject: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completion_date: datetime | None = Field(default=None)
    model: str | None = None
    status: SessionStatus = Field(default=SessionStatus.not_marked)
    total_marks_available: int | None = None
    total_marks_achieved: int | None = None

class Question(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    session_id: str = Field(foreign_key="session.session_id")
    question_number: str
    question_text: str
    status: QuestionStatus = Field(default=QuestionStatus.not_marked)

class Prediction(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    question_id: int = Field(foreign_key="question.id")
    rank: int
    strand: str
    topic: str
    subtopic: str
    spec_sub_section: str
    similarity_score: float
    description: str


class QuestionMark(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    question_id: int = Field(foreign_key="question.id")
    marks_available: int | None = None
    marks_achieved: int | None = None