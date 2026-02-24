"""
Edexcel / Pearson Past Papers Scraper
======================================
Uses the Algolia search API that backs the Pearson qualifications site.
No browser required — all metadata is structured in the Algolia hit payload.

Usage (run from project root):
    python -m paper_scraper --board edexcel [--spec-code CODE] [--all] [--dry-run] [--download]

    --spec-code CODE   Scrape only the given internal spec code (e.g. 9MA0).
                       Defaults to all codes in edexcel_config.SPECS.
    --all              Explicitly scrape all configured specs.
    --dry-run          Print discovered entries without downloading anything.
    --download         Actually download PDFs (default is index-only).
"""

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from paper_scraper import edexcel_config as config
from paper_scraper.downloader import download_pdf, make_session


# ---------------------------------------------------------------------------
# Algolia API
# ---------------------------------------------------------------------------

def _algolia_headers() -> dict:
    return {
        "X-Algolia-Application-Id": config.ALGOLIA_APP_ID,
        "X-Algolia-API-Key": config.ALGOLIA_API_KEY,
        "Content-Type": "application/json",
    }


def fetch_all_hits(algolia_code: str, session: requests.Session) -> list[dict]:
    """Fetch every Algolia hit for the given Pearson taxonomy spec code.

    Paginates automatically (1000 hits/page — typically one page suffices).
    """
    filter_str = f'category:"Pearson-UK:Specification-Code/{algolia_code}"'
    all_hits: list[dict] = []
    page = 0

    while True:
        payload = {
            "params": f"query=&filters={filter_str}&hitsPerPage=1000&page={page}"
        }
        resp = session.post(
            config.ALGOLIA_ENDPOINT,
            headers=_algolia_headers(),
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        hits = data.get("hits", [])
        nb_pages = data.get("nbPages", 1)
        all_hits.extend(hits)
        print(f"    Page {page}: {len(hits)} hits  (total pages: {nb_pages})")

        if page >= nb_pages - 1 or not hits:
            break
        page += 1
        time.sleep(config.PAGE_DELAY_S)

    return all_hits


# ---------------------------------------------------------------------------
# Hit parsing helpers
# ---------------------------------------------------------------------------

def extract_category_value(categories: list[str], prefix: str) -> str | None:
    """Return the value part of the first 'Pearson-UK:{prefix}/{value}' entry."""
    full_prefix = f"Pearson-UK:{prefix}/"
    for cat in categories:
        if cat.startswith(full_prefix):
            return cat[len(full_prefix):]
    return None


def _parse_series(raw: str | None) -> tuple[str | None, int | None]:
    """Convert 'March-2013' → ('march', 2013).  Returns (None, None) on failure."""
    if not raw:
        return None, None
    # Format is typically 'Month-YYYY'
    m = re.match(r"([A-Za-z]+)-(\d{4})", raw)
    if m:
        return m.group(1).lower(), int(m.group(2))
    # Some entries use just a year: '2023'
    m2 = re.match(r"^(\d{4})$", raw)
    if m2:
        return None, int(m2.group(1))
    return raw.lower(), None


def _parse_file_size(size_str: str | None) -> float | None:
    """Convert '385.9 KB' → 385.9.  Returns None if not parseable."""
    if not size_str:
        return None
    m = re.match(r"([\d.]+)\s*KB", size_str, re.IGNORECASE)
    if m:
        return float(m.group(1))
    m2 = re.match(r"([\d.]+)\s*MB", size_str, re.IGNORECASE)
    if m2:
        return round(float(m2.group(1)) * 1024, 2)
    return None


def parse_hit(hit: dict, spec_code: str, spec_config: dict) -> dict | None:
    """Convert a raw Algolia hit into a PastPaper-compatible dict.

    Returns None for gated, non-PDF, or unwanted document types.
    """
    # Skip gated (login-required) content
    if hit.get("gating"):
        return None


    # Only process PDFs
    if hit.get("extension", "").upper() != "PDF":
        return None

    # For specs that share an Algolia code (e.g. the maths family), filter by filename prefix
    url_path_raw: str = hit.get("url", "") or hit.get("id", "")
    filename_raw = url_path_raw.split("/")[-1]
    spec_prefix = spec_config.get("spec_prefix")
    if spec_prefix and not filename_raw.lower().startswith(spec_prefix.lower()):
        return None

    cats: list[str] = hit.get("category", [])

    # Document type → internal code
    raw_doc_type = extract_category_value(cats, "Document-Type")
    paper_type = config.DOC_TYPE_MAP.get(raw_doc_type or "", "UNKNOWN")
    if paper_type not in config.KEEP_TYPES:
        return None

    # Exam series → series name + year
    raw_series = extract_category_value(cats, "Exam-Series")
    series, year = _parse_series(raw_series)

    # Skip papers that are still locked/unreleased
    if year is not None and year > config.MAX_YEAR:
        return None

    # Paper / unit number + tier
    # Pearson encodes tier as a suffix on the Unit value: "Paper-1H" → paper 1, Higher tier.
    # A-level papers have no suffix: "Paper-1" → paper 1, no tier.
    raw_unit = extract_category_value(cats, "Unit")
    tier: str | None = None
    if raw_unit:
        unit_bare = re.sub(r"^Paper-", "", raw_unit, flags=re.IGNORECASE)
        m_tier = re.match(r"^(\d+)([HF])$", unit_bare, re.IGNORECASE)
        if m_tier:
            paper_number = m_tier.group(1)
            tier = "Higher" if m_tier.group(2).upper() == "H" else "Foundation"
        else:
            paper_number = unit_bare
    else:
        paper_number = None

    # Paper name: Pearson's Algolia data doesn't include paper subtitles, so look them up
    # from the config's optional paper_names dict keyed by paper number.
    paper_names = spec_config.get("paper_names", {})
    paper_name = paper_names.get(paper_number) if paper_number else None

    # Filename from URL tail (reuse url_path_raw computed above)
    filename = filename_raw if filename_raw else "unknown.pdf"

    # File size
    file_size_kb = _parse_file_size(hit.get("size"))

    # Stable unique ID for deduplication (prefixed to avoid clashes with AQA)
    content_id = f"edexcel:{hit.get('id') or url_path_raw}"

    local_path = str(
        Path(config.OUTPUT_DIR) / spec_code / str(year or "unknown") / (series or "unknown") / filename
    ).replace("\\", "/")

    return {
        "content_id": content_id,
        "spec_code": spec_code,
        "subject": spec_config["subject"],
        "year": year,
        "series": series,
        "paper_type": paper_type,
        "paper_number": paper_number,
        "paper_name": paper_name,
        "tier": tier,
        "filename": filename,
        "local_path": local_path,
        "source_url": f"{config.BASE_URL}{url_path_raw}",
        "file_size_kb": file_size_kb,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Spec-level orchestration
# ---------------------------------------------------------------------------

def scrape_spec(
    spec_code: str,
    dry_run: bool = True,
    download: bool = False,
    session: requests.Session | None = None,
    debug_hits: bool = False,
) -> list[dict]:
    """Fetch, parse, and optionally download all papers for one spec."""
    if session is None:
        session = make_session()
        session.headers["User-Agent"] = "TopicTracker/1.0 Educational"

    spec_config = config.SPECS[spec_code]
    algolia_code = spec_config["algolia_code"]

    print(f"\n{'='*60}")
    print(f"Scraping {spec_code}: {spec_config['subject']}  (algolia_code={algolia_code})")

    hits = fetch_all_hits(algolia_code, session)
    print(f"  Total hits fetched: {len(hits)}")

    if debug_hits and hits:
        print("\n  [debug] First raw hit fields:")
        for k, v in hits[0].items():
            print(f"    {k!r}: {v!r}")
        print()

    entries: list[dict] = []
    downloaded = 0
    skipped = 0
    errors = 0

    for hit in hits:
        entry = parse_hit(hit, spec_code, spec_config)
        if entry is None:
            continue

        if dry_run or not download:
            print(
                f"  {'[dry-run]' if dry_run else '[index]  '} "
                f"{entry['filename']}  "
                f"({entry['paper_type']} {entry['year']} {entry['series']})"
            )
            entries.append(entry)
            continue

        # Download mode
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

    if download and not dry_run:
        print(f"\n  Done: {downloaded} downloaded, {skipped} skipped, {errors} errors")
    else:
        print(f"  Kept: {len(entries)} QP/MS entries")

    return entries


# ---------------------------------------------------------------------------
# Index helpers (mirrors scraper.py)
# ---------------------------------------------------------------------------

def load_index(path: str) -> list[dict]:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_index(path: str, entries: list[dict]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)


def merge_index(existing: list[dict], new_entries: list[dict]) -> list[dict]:
    existing_ids = {e["content_id"]: i for i, e in enumerate(existing)}
    merged = list(existing)
    for entry in new_entries:
        cid = entry["content_id"]
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
    parser = argparse.ArgumentParser(description="Scrape Edexcel past papers via Algolia API")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--spec-code", help="Single internal spec code (e.g. 9MA0)")
    group.add_argument("--all", dest="all_specs", action="store_true",
                       help="Scrape all configured specs")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print discovered entries without writing anything")
    parser.add_argument("--download", action="store_true",
                        help="Download PDFs (default: index metadata only)")
    parser.add_argument("--debug-hits", action="store_true",
                        help="Print raw Algolia fields for the first hit of each spec (for debugging)")
    args = parser.parse_args()

    if args.spec_code:
        if args.spec_code not in config.SPECS:
            parser.error(f"Unknown spec code '{args.spec_code}'. "
                         f"Available: {', '.join(config.SPECS)}")
        specs_to_scrape = {args.spec_code: config.SPECS[args.spec_code]}
    else:
        specs_to_scrape = config.SPECS

    existing_index = load_index(config.METADATA_FILE)
    all_new_entries: list[dict] = []

    session = requests.Session()
    session.headers["User-Agent"] = "TopicTracker/1.0 Educational"

    for spec_code in specs_to_scrape:
        try:
            entries = scrape_spec(
                spec_code,
                dry_run=args.dry_run,
                download=args.download,
                session=session,
                debug_hits=args.debug_hits,
            )
            all_new_entries.extend(entries)
        except Exception as exc:
            print(f"\n[ERROR] Failed scraping spec {spec_code}: {exc}")
            import traceback
            traceback.print_exc()

    if not args.dry_run:
        merged = merge_index(existing_index, all_new_entries)
        save_index(config.METADATA_FILE, merged)
        print(f"\nIndex saved to {config.METADATA_FILE} ({len(merged)} total entries)")
    else:
        print(f"\n[dry-run] Would have indexed {len(all_new_entries)} entries")


if __name__ == "__main__":
    main()
