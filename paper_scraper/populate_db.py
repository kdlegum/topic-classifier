"""
Populate the PastPaper index table from the exam board API (no downloads).

Usage (run from project root):
    python -m paper_scraper.populate_db --board {aqa,edexcel} [--spec-code CODE]

    --board BOARD      Exam board to index: aqa or edexcel (required)
    --spec-code CODE   Index only the given spec code (e.g. 7357 for AQA, 9MA0 for Edexcel).
                       Defaults to all codes for the selected board.
"""

import argparse
import sys
import time

import requests


def _import_db():
    try:
        from sqlmodel import Session, SQLModel
        from Backend.database import engine
        from Backend.sessionDatabase import PastPaper
        SQLModel.metadata.create_all(engine)
        return Session, engine, PastPaper
    except ImportError as e:
        print(f"Error importing backend modules: {e}")
        print("Run this script from the project root directory.")
        sys.exit(1)


def upsert_entry(db, PastPaper, entry: dict) -> bool:
    """Insert or refresh a PastPaper row. Returns True if newly inserted."""
    existing = db.get(PastPaper, entry["content_id"])
    if existing:
        existing.local_path = entry["local_path"]
        existing.source_url = entry["source_url"]
        existing.scraped_at = entry["scraped_at"]
        if entry.get("file_size_kb") is not None:
            existing.file_size_kb = entry["file_size_kb"]
        db.add(existing)
        return False
    else:
        db.add(PastPaper(
            content_id=entry["content_id"],
            spec_code=entry["spec_code"],
            subject=entry["subject"],
            year=entry["year"],
            series=entry["series"],
            paper_type=entry["paper_type"],
            paper_number=entry.get("paper_number"),
            paper_name=entry.get("paper_name"),
            tier=entry.get("tier"),
            filename=entry["filename"],
            local_path=entry["local_path"],
            source_url=entry["source_url"],
            file_size_kb=entry.get("file_size_kb"),
            scraped_at=entry["scraped_at"],
        ))
        return True


def run_aqa(spec_code: str | None):
    from paper_scraper import aqa_config as config
    from paper_scraper.aqa_scraper import fetch_all_results, build_entry

    specs = {spec_code: config.SPECS.get(spec_code, "Unknown")} if spec_code else config.SPECS

    Session, engine, PastPaper = _import_db()
    http = requests.Session()
    http.headers["User-Agent"] = "TopicTracker/1.0 Educational"

    total_processed = 0
    total_inserted = 0

    for code, subject in specs.items():
        print(f"\nIndexing {code}: {subject}")
        try:
            results = fetch_all_results(code, http)
        except Exception as e:
            print(f"  [ERROR] Failed to fetch results for {code}: {e}")
            continue

        entries = [
            build_entry(r, code, subject)
            for r in results
        ]
        entries = [e for e in entries if e["paper_type"] in ("QP", "MS") and not e.get("is_modified")]
        print(f"  {len(entries)} QP/MS entries found")

        with Session(engine) as db:
            for entry in entries:
                if upsert_entry(db, PastPaper, entry):
                    total_inserted += 1
                total_processed += 1
            db.commit()

        print(f"  Done: {len(entries)} entries committed")
        time.sleep(config.PAGE_DELAY_S)

    print(f"\nFinished. Processed {total_processed} entries, inserted {total_inserted} new rows.")


def run_edexcel(spec_code: str | None):
    from paper_scraper import edexcel_config as config
    from paper_scraper.edexcel_scraper import fetch_all_hits, parse_hit

    if spec_code:
        if spec_code not in config.SPECS:
            print(f"Unknown spec code '{spec_code}'. Available: {', '.join(config.SPECS)}")
            sys.exit(1)
        specs = {spec_code: config.SPECS[spec_code]}
    else:
        specs = config.SPECS

    Session, engine, PastPaper = _import_db()
    http = requests.Session()
    http.headers["User-Agent"] = "TopicTracker/1.0 Educational"

    total_processed = 0
    total_inserted = 0

    for code, spec_config in specs.items():
        print(f"\nIndexing {code}: {spec_config['subject']}")
        try:
            hits = fetch_all_hits(spec_config["algolia_code"], http)
        except Exception as e:
            print(f"  [ERROR] Failed to fetch hits for {code}: {e}")
            continue

        entries = [parse_hit(h, code, spec_config) for h in hits]
        entries = [e for e in entries if e is not None]
        print(f"  {len(entries)} QP/MS entries found")

        with Session(engine) as db:
            for entry in entries:
                if upsert_entry(db, PastPaper, entry):
                    total_inserted += 1
                total_processed += 1
            db.commit()

        print(f"  Done: {len(entries)} entries committed")
        time.sleep(config.PAGE_DELAY_S)

    print(f"\nFinished. Processed {total_processed} entries, inserted {total_inserted} new rows.")


def main():
    parser = argparse.ArgumentParser(
        description="Populate PastPaper DB from exam board API (no downloads)"
    )
    parser.add_argument("--board", required=True, choices=["aqa", "edexcel"],
                        help="Exam board to index")
    parser.add_argument("--spec-code", help="Single spec code to index")
    args = parser.parse_args()

    if args.board == "aqa":
        run_aqa(args.spec_code)
    else:
        run_edexcel(args.spec_code)


if __name__ == "__main__":
    main()
