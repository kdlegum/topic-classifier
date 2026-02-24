"""
AQA Past Papers Scraper
=======================
Uses the undocumented AQA JSON search API — no browser required.

Usage:
    python -m paper_scraper --board aqa [--spec-code CODE] [--dry-run]

    --spec-code CODE   Scrape only the given AQA spec code (e.g. 7367).
                       Defaults to all codes in aqa_config.SPECS.
    --dry-run          Print discovered entries without downloading anything.
"""

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from paper_scraper import aqa_config as config
from paper_scraper.downloader import download_pdf, make_session


# ---------------------------------------------------------------------------
# AQA Search API
# ---------------------------------------------------------------------------

API_URL = "https://www.aqa.org.uk/api/search"
API_PARAMS_BASE = {
    "type": "aqaResource",
    "location": "/find-past-papers-and-mark-schemes",
    "prefilter": "scope",
    "scope": "findPastPapers",
    "facets": "subject,qualification,qualificationLevel,specCode,componentCodes,"
              "secondaryResourceType,examSeries,examTier,printSize",
    "sort": "relevance",
    "limit": "100",
}


def fetch_all_results(spec_code: str, session: requests.Session) -> list[dict]:
    """Fetch all API results for a given spec code, paginating as needed."""
    all_results = []
    page = 1

    while True:
        params = {**API_PARAMS_BASE, "specCode": spec_code, "page": str(page)}
        resp = session.get(API_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        results = data.get("results", [])
        total_hits = data.get("hits", 0)
        all_results.extend(results)

        print(f"    Page {page}: {len(results)} results  (total hits: {total_hits})")

        if len(all_results) >= total_hits or not results:
            break
        page += 1
        time.sleep(config.PAGE_DELAY_S)

    return all_results


# ---------------------------------------------------------------------------
# Metadata parsing
# ---------------------------------------------------------------------------

MONTH_MAP = {
    "jan": "january", "feb": "february", "mar": "march", "apr": "april",
    "may": "may",     "jun": "june",     "jul": "july",  "aug": "august",
    "sep": "september","oct": "october", "nov": "november","dec": "december",
}

TYPE_MAP = {
    "question paper": "QP",
    "mark scheme": "MS",
    "insert": "INSERT",
    "data sheet": "DATA",
    "data booklet": "DATA",
    "formula sheet": "FORMULA",
    "answer booklet": "AB",
    "examiner report": "ER",
}


def parse_content_id(content_id: str) -> dict:
    """Extract year, series and filename from AQA contentId.

    contentId examples:
      sample-papers-and-mark-schemes.2023.june.AQA-73671-QP-JUN23_PDF
      resources.mathematics.AQA-73671-SQP_PDF
    """
    meta: dict = {}

    bare = content_id
    if bare.endswith("_PDF"):
        bare = bare[:-4]

    filename_stem = bare.split(".")[-1]  # e.g. AQA-73671-QP-JUN23
    meta["filename"] = filename_stem + ".pdf"

    segments = bare.split(".")
    year_match = re.match(r"^(20\d{2})$", segments[1]) if len(segments) > 1 else None
    meta["year"] = int(year_match.group(1)) if year_match else None

    # Series — third segment if it's a month word
    if len(segments) > 2:
        s = segments[2].lower()
        meta["series"] = s if s in MONTH_MAP.values() or s in MONTH_MAP else None
    else:
        meta["series"] = None

    return meta


def parse_display_name(display_name: str) -> dict:
    """Extract paper_type and paper_number from the displayName field.

    displayName examples:
      "Question paper: Paper 1 - June 2023"
      "Mark scheme: Paper 3 Mechanics - November 2020"
      "Question paper (Modified A4 18pt): Paper 1 - June 2023"
    """
    meta: dict = {}

    colon_pos = display_name.find(":")
    if colon_pos != -1:
        # Handle "(Modified ...)" suffix before the colon text
        type_raw = re.sub(r"\s*\(.*?\)", "", display_name[:colon_pos]).strip().lower()
        meta["paper_type"] = TYPE_MAP.get(type_raw, type_raw.upper())
        meta["is_modified"] = "modified" in display_name[:colon_pos].lower()
    else:
        meta["paper_type"] = "UNKNOWN"
        meta["is_modified"] = False

    paper_match = re.search(r"Paper\s+(\d+[A-Za-z]?)", display_name, re.IGNORECASE)
    meta["paper_number"] = paper_match.group(1) if paper_match else None

    # Paper name: descriptive suffix after the paper number, e.g. "Mechanics" in "Paper 3 Mechanics"
    paper_name_match = re.search(
        r"Paper\s+\d+[A-Za-z]?\s+([A-Za-z][A-Za-z ]*?)(?=\s*-|\s*$)",
        display_name, re.IGNORECASE,
    )
    meta["paper_name"] = paper_name_match.group(1).strip() if paper_name_match else None

    tier_match = re.search(r"\b(Higher|Foundation)\b", display_name, re.IGNORECASE)
    meta["tier"] = tier_match.group(1).capitalize() if tier_match else None

    return meta


def build_entry(result: dict, spec_code: str, subject: str) -> dict:
    content_id = result["contentId"]
    display_name = result.get("displayName", "")

    id_meta = parse_content_id(content_id)
    name_meta = parse_display_name(display_name)

    year = id_meta["year"]
    series = id_meta["series"]
    filename = id_meta["filename"]
    paper_type = name_meta["paper_type"]

    # Tier: prefer direct API field, fall back to display name parse
    raw_tier = result.get("tier") or result.get("examTier")
    tier = raw_tier or name_meta.get("tier")

    # Construct download URL from contentId — keep _PDF suffix, it's part of the path
    source_url = f"{config.BASE_URL}/files/{content_id}"

    local_path = str(
        Path(config.OUTPUT_DIR) / spec_code / str(year or "unknown") / (series or "unknown") / filename
    ).replace("\\", "/")

    return {
        "spec_code": spec_code,
        "subject": subject,
        "year": year,
        "series": series,
        "paper_type": paper_type,
        "paper_number": name_meta["paper_number"],
        "paper_name": name_meta["paper_name"],
        "is_modified": name_meta["is_modified"],
        "tier": tier,
        "filename": filename,
        "local_path": local_path,
        "source_url": source_url,
        "display_name": display_name,
        "content_id": content_id,
        "file_size_kb": None,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Main scraping logic
# ---------------------------------------------------------------------------

def scrape_spec(spec_code: str, subject: str, dry_run: bool,
                session: requests.Session) -> list[dict]:
    print(f"\n{'='*60}")
    print(f"Scraping spec {spec_code}: {subject}")

    results = fetch_all_results(spec_code, session)
    print(f"  Total results fetched: {len(results)}")

    entries = []
    downloaded = 0
    skipped = 0
    errors = 0

    for result in results:
        entry = build_entry(result, spec_code, subject)

        # Only keep standard QP and MS — skip modified formats, examiner reports, etc.
        if entry["paper_type"] not in ("QP", "MS") or entry["is_modified"]:
            continue

        if entry["year"] is not None and entry["year"] > config.MAX_YEAR:
            continue

        if dry_run:
            print(f"  [dry-run] {entry['filename']}  "
                  f"({entry['paper_type']} {entry['year']} {entry['series']})")
            entries.append(entry)
            continue

        dest = entry["local_path"]
        try:
            did_download = download_pdf(entry["source_url"], dest, session, config.DOWNLOAD_DELAY_S)
            if did_download:
                size_kb = os.path.getsize(dest) / 1024
                entry["file_size_kb"] = round(size_kb, 2)
                print(f"  [download] {entry['filename']}  ({size_kb:.1f} KB)")
                downloaded += 1
            else:
                if os.path.exists(dest):
                    entry["file_size_kb"] = round(os.path.getsize(dest) / 1024, 2)
                print(f"  [skip]     {entry['filename']}")
                skipped += 1
        except Exception as exc:
            print(f"  [error]    {entry['filename']}  — {exc}")
            errors += 1

        entries.append(entry)

    if not dry_run:
        print(f"\n  Done: {downloaded} downloaded, {skipped} skipped, {errors} errors")

    return entries


# ---------------------------------------------------------------------------
# Index helpers
# ---------------------------------------------------------------------------

def load_index(path: str) -> list[dict]:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_index(path: str, entries: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)


def merge_index(existing: list[dict], new_entries: list[dict]) -> list[dict]:
    existing_ids = {e["content_id"]: i for i, e in enumerate(existing)}
    merged = list(existing)
    for entry in new_entries:
        cid = entry.get("content_id", entry.get("source_url"))
        if cid not in existing_ids:
            merged.append(entry)
            existing_ids[cid] = len(merged) - 1
        elif entry.get("file_size_kb") is not None:
            merged[existing_ids[cid]]["file_size_kb"] = entry["file_size_kb"]
    return merged


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Scrape AQA past papers via JSON API")
    parser.add_argument("--spec-code", help="Single spec code to scrape (e.g. 7367)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print discovered entries without downloading")
    args = parser.parse_args()

    if args.spec_code:
        specs_to_scrape = {args.spec_code: config.SPECS.get(args.spec_code, "Unknown")}
    else:
        specs_to_scrape = config.SPECS

    existing_index = load_index(config.METADATA_FILE)
    all_new_entries: list[dict] = []

    session = make_session()
    session.headers["User-Agent"] = "TopicTracker/1.0 Educational"

    for spec_code, subject in specs_to_scrape.items():
        try:
            entries = scrape_spec(spec_code, subject, args.dry_run, session)
            all_new_entries.extend(entries)
        except Exception as exc:
            print(f"\n[ERROR] Failed scraping spec {spec_code}: {exc}")
            import traceback; traceback.print_exc()

    if not args.dry_run:
        merged = merge_index(existing_index, all_new_entries)
        save_index(config.METADATA_FILE, merged)
        print(f"\nIndex saved to {config.METADATA_FILE} ({len(merged)} total entries)")
    else:
        print(f"\n[dry-run] Would have processed {len(all_new_entries)} entries")


if __name__ == "__main__":
    main()
