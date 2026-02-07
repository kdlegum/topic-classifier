"""
Seed script: reads topics.json and populates the Specification, Topic, and Subtopic tables.
Idempotent — clears and re-inserts on every run.

Run from Backend/ directory:  python seed_specs.py
"""

import json
from pathlib import Path
from sqlmodel import Session, select
from database import engine
from sessionDatabase import Specification, Topic, Subtopic
from sqlmodel import SQLModel

INPUT_FILE = Path("topics.json")


def clear_spec_tables(db: Session):
    """Delete all rows from Subtopic, Topic, Specification (in FK order)."""
    for row in db.exec(select(Subtopic)).all():
        db.delete(row)
    for row in db.exec(select(Topic)).all():
        db.delete(row)
    for row in db.exec(select(Specification)).all():
        db.delete(row)
    db.commit()


def seed():
    with INPUT_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        specs = [data]
    elif isinstance(data, list):
        specs = data
    else:
        raise TypeError("topics.json must be a dict or a list of dicts")

    with Session(engine) as db:
        clear_spec_tables(db)

        spec_count = 0
        topic_count = 0
        subtopic_count = 0

        for spec_data in specs:
            db_spec = Specification(
                qualification=spec_data["Qualification"],
                subject=spec_data["Subject"],
                exam_board=spec_data["Exam Board"],
                spec_code=spec_data["Specification"],
            )
            db.add(db_spec)
            db.flush()  # get db_spec.id
            spec_count += 1

            for topic_data in spec_data.get("Topics", []):
                db_topic = Topic(
                    specification_id=db_spec.id,
                    topic_id_within_spec=topic_data["Topic_id"],
                    specification_section=topic_data["Specification_section"],
                    strand=topic_data["Strand"],
                    topic_name=topic_data["Topic_name"],
                )
                db.add(db_topic)
                db.flush()  # get db_topic.id
                topic_count += 1

                for sub_data in topic_data.get("Sub_topics", []):
                    db_subtopic = Subtopic(
                        topic_db_id=db_topic.id,
                        subtopic_id=sub_data["subtopic_id"],
                        specification_section_sub=sub_data["Specification_section_sub"],
                        subtopic_name=sub_data["Sub_topic_name"],
                        description=sub_data["description"],
                    )
                    db.add(db_subtopic)
                    subtopic_count += 1

        db.commit()

    print(f"Seeded {spec_count} specifications, {topic_count} topics, {subtopic_count} subtopics.")


if __name__ == "__main__":
    SQLModel.metadata.create_all(engine)
    seed()
