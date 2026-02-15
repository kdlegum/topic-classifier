from sqlmodel import SQLModel
from sqlalchemy import text
from database import engine
from sessionDatabase import (
    Session, Question, Prediction, QuestionMark, UserCorrection,
    Specification, Topic, Subtopic, UserModuleSelection, SessionStrand,
    UserSpecSelection, QuestionLocation, RevisionAttempt,
)

SQLModel.metadata.create_all(engine)

# Migrations for columns added after initial table creation
migrations = [
    "ALTER TABLE session ADD COLUMN pdf_filename VARCHAR DEFAULT NULL",
]

with engine.begin() as conn:
    for sql in migrations:
        try:
            conn.execute(text(sql))
            print(f"Migration applied: {sql}")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                pass  # Column already exists
            else:
                print(f"Migration skipped ({e})")

print("Database created successfully.")
