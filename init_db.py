from sqlmodel import SQLModel, create_engine
from sessionDatabase import Session, Question, ClassificationResult

engine = create_engine("sqlite:///exam_app.db")

SQLModel.metadata.create_all(engine)

print("Database created successfully.")
