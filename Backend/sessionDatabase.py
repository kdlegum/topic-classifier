from sqlmodel import Field, Session, SQLModel, create_engine
from typing import Optional
import uuid
from datetime import datetime
from enum import Enum

"""
Session (exam paper, model = X)
  └── Question
        ├── Prediction (rank 1)
        ├── Prediction (rank 2)
        └── Prediction (rank 3)

Specification
  └── Topic
        └── Subtopic
"""

class QuestionStatus(str, Enum):
    not_marked = "not_marked"
    marked = "marked"

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
    pdf_filename: str | None = Field(default=None)

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

class UserCorrection(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    question_id: int = Field(foreign_key="question.id", index=True)
    subtopic_id: str
    exam_board: str
    spec_code: str
    strand: str
    topic: str
    subtopic: str
    spec_sub_section: str
    description: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Specification data models ───────────────────────────────────────

class Specification(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    qualification: str
    subject: str
    exam_board: str
    spec_code: str = Field(unique=True, index=True)
    optional_modules: bool = Field(default=False)
    has_math: bool = Field(default=False)
    creator_id: str | None = Field(default=None, index=True)
    creator_is_guest: bool = Field(default=False)
    is_reviewed: bool = Field(default=False)
    description: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class UserModuleSelection(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    is_guest: bool = Field(default=True)
    spec_code: str = Field(index=True)
    strand: str

class SessionStrand(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    session_id: str = Field(foreign_key="session.session_id", index=True)
    strand: str

class UserSpecSelection(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    is_guest: bool = Field(default=True)
    spec_code: str = Field(index=True)
    added_at: datetime = Field(default_factory=datetime.utcnow)

class Topic(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    specification_id: int = Field(foreign_key="specification.id")
    topic_id_within_spec: int
    specification_section: str
    strand: str
    topic_name: str

class Subtopic(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    topic_db_id: int = Field(foreign_key="topic.id")
    subtopic_id: str
    specification_section_sub: str
    subtopic_name: str
    description: str


class QuestionLocation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    question_id: int = Field(foreign_key="question.id", index=True)
    start_page: int       # 0-indexed
    start_y: float        # top of question (PDF points from page top)
    end_page: int         # may differ from start_page for multi-page questions
    end_y: float          # bottom of question content (before answer lines)