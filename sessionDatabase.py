from sqlmodel import Field, Session, SQLModel, create_engine
import uuid
from datetime import datetime



class Session(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()), index=True, unique=True)
    exam_board: str
    subject: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Question(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    session_id: str = Field(foreign_key="session.session_id")
    question_number: str
    question_text: str

class ClassificationResult(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    question_id: int = Field(foreign_key="question.id")
    strand: str
    topic: str
    subtopic: str
    spec_sub_section: str
    confidence: float