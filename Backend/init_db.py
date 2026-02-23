from sqlmodel import SQLModel
from sqlalchemy import text
from database import engine
from sessionDatabase import (
    Session, Question, Prediction, QuestionMark, UserCorrection,
    Specification, Topic, Subtopic, UserModuleSelection, SessionStrand,
    UserSpecSelection, QuestionLocation, RevisionAttempt, UserTierSelection,
    PastPaper,
)

SQLModel.metadata.create_all(engine)

migrations = [
    "ALTER TABLE session ADD COLUMN pdf_filename VARCHAR DEFAULT NULL",
    "ALTER TABLE specification ADD COLUMN is_hidden BOOLEAN DEFAULT FALSE",
    "ALTER TABLE specification ADD COLUMN content_hash VARCHAR DEFAULT NULL",
    "ALTER TABLE session ADD COLUMN mark_scheme_filename VARCHAR DEFAULT NULL",
    "ALTER TABLE session ADD COLUMN no_spec BOOLEAN DEFAULT FALSE",
    "ALTER TABLE session ADD COLUMN name TEXT DEFAULT NULL",
    "ALTER TABLE pastpaper ADD COLUMN tier VARCHAR DEFAULT NULL",
    "ALTER TABLE pastpaper ADD COLUMN paper_name VARCHAR DEFAULT NULL",
    "ALTER TABLE session ADD COLUMN paper_number VARCHAR DEFAULT NULL",
    "ALTER TABLE session ADD COLUMN paper_name VARCHAR DEFAULT NULL",
    "ALTER TABLE session ADD COLUMN paper_year INTEGER DEFAULT NULL",
    "ALTER TABLE session ADD COLUMN paper_series VARCHAR DEFAULT NULL",
]

for sql in migrations:
    try:
        with engine.begin() as conn:
            conn.execute(text(sql))
            print(f"Migration applied: {sql}")
    except Exception as e:
        if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
            pass
        else:
            print(f"Migration skipped ({e})")

print("Database created successfully.")
