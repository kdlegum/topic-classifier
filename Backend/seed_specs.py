"""
Seed script: reads spec JSON files and upserts the Specification, Topic, and Subtopic tables.
Only touches seeded specs (creator_id IS NULL) — user-created specs are left untouched.
Optionally rebuilds the subtopics_index.json used for classification embeddings.

Run from Backend/ directory:
  python seed_specs.py ../spec_generation              # seed DB only
  python seed_specs.py ../spec_generation --build-index # seed DB + rebuild index
  python seed_specs.py --build-index                   # falls back to ../spec_generation
"""

import argparse
import json
from pathlib import Path
from sqlmodel import Session, select
from database import engine
from sessionDatabase import Specification, Topic, Subtopic
from subtopicsBuilder import build_subtopics_index
from sqlmodel import SQLModel

DEFAULT_INPUT = Path("../spec_generation")
INDEX_OUTPUT = Path("subtopics_index.json")


def collect_inputs(paths: list[str]) -> list[Path]:
    """Resolve CLI paths into a list of JSON file paths."""
    if paths:
        result = []
        for arg in paths:
            p = Path(arg)
            if p.is_dir():
                result.extend(sorted(p.glob("*.json")))
            elif p.is_file():
                result.append(p)
            else:
                print(f"Warning: skipping {arg} (not found)")
        return result
    if DEFAULT_INPUT.is_dir():
        return sorted(DEFAULT_INPUT.glob("*.json"))
    if DEFAULT_INPUT.is_file():
        return [DEFAULT_INPUT]
    return []


def load_specs(files: list[Path]) -> list[dict]:
    """Load and merge specs from multiple JSON files."""
    specs = []
    for f in files:
        with f.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            specs.append(data)
        elif isinstance(data, list):
            specs.extend(data)
        else:
            print(f"Warning: skipping {f.name} (unexpected type {type(data).__name__})")
    return specs


def clear_seeded_spec(db: Session, spec_code: str):
    """Delete a seeded spec and its topics/subtopics (by spec_code, only if creator_id IS NULL)."""
    existing = db.exec(
        select(Specification).where(
            Specification.spec_code == spec_code,
            Specification.creator_id.is_(None),  # type: ignore[union-attr]
        )
    ).first()
    if not existing:
        return
    # Delete subtopics → topics → spec (FK order)
    for topic in db.exec(select(Topic).where(Topic.specification_id == existing.id)).all():
        for sub in db.exec(select(Subtopic).where(Subtopic.topic_db_id == topic.id)).all():
            db.delete(sub)
        db.delete(topic)
    db.delete(existing)


def seed_db(specs: list[dict]):
    """Upsert seeded specs into the database, leaving user-created specs untouched."""
    with Session(engine) as db:
        spec_count = 0
        topic_count = 0
        subtopic_count = 0

        for spec_data in specs:
            spec_code = spec_data["Specification"]

            # Remove old seeded version if it exists
            clear_seeded_spec(db, spec_code)
            db.flush()

            db_spec = Specification(
                qualification=spec_data["Qualification"],
                subject=spec_data["Subject"],
                exam_board=spec_data["Exam Board"],
                spec_code=spec_code,
                optional_modules=spec_data.get("optional_modules", False),
                has_math=spec_data.get("has_math", False),
                is_reviewed=True,
                creator_id=None,
                creator_is_guest=False,
            )
            db.add(db_spec)
            db.flush()
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
                db.flush()
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


def write_index(specs: list[dict]):
    """Build and write subtopics_index.json."""
    index = build_subtopics_index(specs)
    with INDEX_OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    print(f"Built subtopics index: {len(index)} entries → {INDEX_OUTPUT}")


def main():
    parser = argparse.ArgumentParser(description="Seed spec data into DB and optionally rebuild subtopics index.")
    parser.add_argument("paths", nargs="*", help="JSON files or directories to load (default: ../spec_generation)")
    parser.add_argument("--build-index", action="store_true", help="Also rebuild subtopics_index.json")
    args = parser.parse_args()

    files = collect_inputs(args.paths)
    if not files:
        print("No input files found. Pass a directory or file paths as arguments.")
        raise SystemExit(1)

    specs = load_specs(files)
    print(f"Loaded {len(specs)} spec(s) from {len(files)} file(s).")

    SQLModel.metadata.create_all(engine)
    seed_db(specs)

    if args.build_index:
        write_index(specs)


if __name__ == "__main__":
    main()
