"""
Populate the PastPaper index table from the AQA search API (no downloads).

Usage (run from project root):
    python -m paper_scraper.populate_db [--spec-code CODE]

    --spec-code CODE   Index only the given spec code (e.g. 7357).
                       Defaults to all codes in config.SPECS.
"""

import argparse
import sys
import time

import requests

from paper_scraper import config
from paper_scraper.scraper import fetch_all_results, build_entry


def main():
    parser = argparse.ArgumentParser(
        description="Populate PastPaper DB index from AQA API (no downloads)"
    )
    parser.add_argument("--spec-code", help="Single spec code to index (e.g. 7357)")
    args = parser.parse_args()

    if args.spec_code:
        specs = {args.spec_code: config.SPECS.get(args.spec_code, "Unknown")}
    else:
        specs = config.SPECS

    # Import DB components (must run from project root so Backend.* is resolvable)
    try:
        from sqlmodel import Session, select
        from Backend.database import engine
        from Backend.sessionDatabase import PastPaper
        from sqlmodel import SQLModel
        SQLModel.metadata.create_all(engine)
    except ImportError as e:
        print(f"Error importing backend modules: {e}")
        print("Run this script from the project root directory.")
        sys.exit(1)

    http = requests.Session()
    http.headers["User-Agent"] = "TopicTracker/1.0 Educational"

    total_processed = 0
    total_upserted = 0

    for spec_code, subject in specs.items():
        print(f"\nIndexing {spec_code}: {subject}")
        try:
            results = fetch_all_results(spec_code, http)
        except Exception as e:
            print(f"  [ERROR] Failed to fetch results for {spec_code}: {e}")
            continue

        entries = []
        for result in results:
            entry = build_entry(result, spec_code, subject)
            # Only index standard QP and MS; skip modified formats and others
            if entry["paper_type"] not in ("QP", "MS") or entry.get("is_modified"):
                continue
            entries.append(entry)

        print(f"  {len(entries)} QP/MS entries found")

        with Session(engine) as db:
            for entry in entries:
                existing = db.get(PastPaper, entry["content_id"])
                if existing:
                    # Refresh mutable fields in case URLs or paths changed
                    existing.local_path = entry["local_path"]
                    existing.source_url = entry["source_url"]
                    existing.scraped_at = entry["scraped_at"]
                    db.add(existing)
                else:
                    db.add(PastPaper(
                        content_id=entry["content_id"],
                        spec_code=entry["spec_code"],
                        subject=entry["subject"],
                        year=entry["year"],
                        series=entry["series"],
                        paper_type=entry["paper_type"],
                        paper_number=entry["paper_number"],
                        filename=entry["filename"],
                        local_path=entry["local_path"],
                        source_url=entry["source_url"],
                        file_size_kb=entry["file_size_kb"],
                        scraped_at=entry["scraped_at"],
                    ))
                    total_upserted += 1
                total_processed += 1
            db.commit()

        print(f"  Done: {len(entries)} entries committed")
        time.sleep(config.PAGE_DELAY_S)

    print(f"\nFinished. Processed {total_processed} entries, inserted {total_upserted} new rows.")


if __name__ == "__main__":
    main()
