"""
Seed script: reads spec JSON files and upserts the Specification, Topic, and Subtopic tables.
Only touches seeded specs (creator_id IS NULL) — user-created specs are left untouched.
Specs whose content hasn't changed (same SHA-256 hash) are skipped automatically.
Optionally rebuilds the subtopics_index.json used for classification embeddings.

Run from Backend/ directory:
  python seed_specs.py ../spec_generation              # seed DB only (skips unchanged)
  python seed_specs.py ../spec_generation --build-index # seed DB + rebuild index
  python seed_specs.py --build-index                   # falls back to ../spec_generation
  python seed_specs.py --clean                         # remove seeded specs not in input files
"""

import argparse
import hashlib
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
    """Load and merge specs from multiple JSON files, skipping non-spec entries."""
    specs = []
    for f in files:
        with f.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            entries = [data]
        elif isinstance(data, list):
            entries = data
        else:
            print(f"Warning: skipping {f.name} (unexpected type {type(data).__name__})")
            continue
        for entry in entries:
            if isinstance(entry, dict) and "Specification" in entry:
                specs.append(entry)
            else:
                print(f"Warning: skipping non-spec entry in {f.name}")
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
    # Delete subtopics -> topics -> spec (FK order, flush between levels)
    topics = db.exec(select(Topic).where(Topic.specification_id == existing.id)).all()
    for topic in topics:
        for sub in db.exec(select(Subtopic).where(Subtopic.topic_db_id == topic.id)).all():
            db.delete(sub)
    db.flush()
    for topic in topics:
        db.delete(topic)
    db.flush()
    db.delete(existing)


def clean_stale_specs(db: Session, keep_codes: set[str]):
    """Remove seeded specs whose spec_code is not in keep_codes, with user confirmation."""
    all_seeded = db.exec(
        select(Specification).where(Specification.creator_id.is_(None))  # type: ignore[union-attr]
    ).all()
    stale = [s for s in all_seeded if s.spec_code not in keep_codes]
    if not stale:
        print("No stale seeded specs found.")
        return
    print(f"\nThe following {len(stale)} seeded spec(s) will be deleted:")
    for spec in stale:
        print(f"  - {spec.spec_code} ({spec.subject} / {spec.exam_board})")
    answer = input("\nProceed with deletion? [y/N] ").strip().lower()
    if answer != "y":
        print("Skipped clean.")
        return
    for spec in stale:
        topics = db.exec(select(Topic).where(Topic.specification_id == spec.id)).all()
        for topic in topics:
            for sub in db.exec(select(Subtopic).where(Subtopic.topic_db_id == topic.id)).all():
                db.delete(sub)
        db.flush()
        for topic in topics:
            db.delete(topic)
        db.flush()
        db.delete(spec)
    print(f"Cleaned {len(stale)} stale seeded spec(s).")


def spec_hash(spec_data: dict) -> str:
    """Compute a stable SHA-256 hash of a spec dict (sorted keys, UTF-8)."""
    canonical = json.dumps(spec_data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def seed_db(specs: list[dict]):
    """Upsert seeded specs into the database, leaving user-created specs untouched.
    Specs whose content hash hasn't changed are skipped."""
    with Session(engine) as db:
        spec_count = 0
        skipped_count = 0
        topic_count = 0
        subtopic_count = 0

        for spec_data in specs:
            spec_code = spec_data.get("Specification")
            if not spec_code:
                continue

            new_hash = spec_hash(spec_data)

            # Skip if already seeded with identical content
            existing = db.exec(
                select(Specification).where(
                    Specification.spec_code == spec_code,
                    Specification.creator_id.is_(None),  # type: ignore[union-attr]
                )
            ).first()
            if existing and existing.content_hash == new_hash:
                skipped_count += 1
                continue

            # Remove old seeded version before reinserting
            if existing:
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
                content_hash=new_hash,
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

    parts = [f"Seeded {spec_count} spec(s), {topic_count} topics, {subtopic_count} subtopics."]
    if skipped_count:
        parts.append(f"Skipped {skipped_count} unchanged spec(s).")
    print(" ".join(parts))


def write_index(specs: list[dict]):
    """Build and write subtopics_index.json."""
    index = build_subtopics_index(specs)
    with INDEX_OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    print(f"Built subtopics index: {len(index)} entries -> {INDEX_OUTPUT}")


def main():
    parser = argparse.ArgumentParser(description="Seed spec data into DB and optionally rebuild subtopics index.")
    parser.add_argument("paths", nargs="*", help="JSON files or directories to load (default: ../spec_generation)")
    parser.add_argument("--build-index", action="store_true", help="Also rebuild subtopics_index.json")
    parser.add_argument("--clean", action="store_true", help="Remove seeded specs not present in the input files")
    args = parser.parse_args()

    files = collect_inputs(args.paths)
    if not files:
        print("No input files found. Pass a directory or file paths as arguments.")
        raise SystemExit(1)

    specs = load_specs(files)
    print(f"Loaded {len(specs)} spec(s) from {len(files)} file(s).")

    SQLModel.metadata.create_all(engine)
    seed_db(specs)

    if args.clean:
        keep_codes = {s["Specification"] for s in specs}
        with Session(engine) as db:
            clean_stale_specs(db, keep_codes)
            db.commit()

    if args.build_index:
        write_index(specs)


if __name__ == "__main__":
    main()
