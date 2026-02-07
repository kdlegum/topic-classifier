from sqlmodel import SQLModel
from database import engine
from sessionDatabase import (
    Session, Question, Prediction, QuestionMark, UserCorrection,
    Specification, Topic, Subtopic,
)

SQLModel.metadata.create_all(engine)

print("Database created successfully.")
