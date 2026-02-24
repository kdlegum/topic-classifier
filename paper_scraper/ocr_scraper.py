"""
OCR Past Papers Scraper
=======================
Uses OCR's undocumented jQuery-based resource filter API.
No browser required — two POST requests per qualification.

Flow per spec:
  1. POST /resource/getlevels/          → confirm the level (e.g. "A Level") is available
  2. POST /resource/filterresourcesbysubject/  → returns resources as HTML (~10 s)
  3. Parse HTML with BeautifulSoup to extract PDF links and metadata

Usage (run from project root):
    python -m paper_scraper --board ocr [--spec-code CODE] [--all] [--dry-run] [--download]

    --spec-code CODE   Scrape only the given spec code (e.g. H640).
    --all              Explicitly scrape all configured specs.
    --dry-run          Print discovered entries without writing anything.
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
from bs4 import BeautifulSoup

from paper_scraper import ocr_config as config
from paper_scraper.downloader import download_pdf, make_session


# ---------------------------------------------------------------------------
# OCR API helpers
# ---------------------------------------------------------------------------

_HEADERS = {
    "User-Agent": "TopicTracker/1.0 Educational",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.ocr.org.uk/",
}


def fetch_levels(qualification_value: int, session: requests.Session) -> list[str]:
    """Return the list of available qualification level names for this subject.

    Response: [{"value": 383897, "description": "A Level"}, ...]
    """
    resp = session.post(
        config.LEVELS_ENDPOINT,
        data={"qualification": qualification_value},
        headers=_HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list):
        return [item.get("description", "") for item in data]
    return []


def fetch_resources_html(
    qualification_value: int,
    level: str,
    page_id: str,
    session: requests.Session,
) -> str:
    """Fetch the resource filter HTML for the given qualification + level."""
    payload: dict = {
        "qualification": qualification_value,
        "level": level,
        "templateId": config.TEMPLATE_ID,
        "resultHeader": config.RESULT_HEADER,
        "errorMessage": config.ERROR_MESSAGE,
    }
    if page_id:
        payload["pageId"] = page_id
    for i, rt in enumerate(config.RESOURCE_TYPES):
        payload[f"resourcetypes[{i}]"] = rt

    resp = session.post(
        config.FILTER_ENDPOINT,
        data=payload,
        headers=_HEADERS,
        timeout=60,
    )
    resp.raise_for_status()
    return resp.text


# ---------------------------------------------------------------------------
# HTML parsing
# ---------------------------------------------------------------------------

def _parse_doc_type(title: str) -> str:
    lower = title.lower()
    # Check answer book before question paper to avoid misclassification
    if "answer book" in lower or "answer booklet" in lower:
        return "AB"
    # PAB = Pre-released Answer Booklet; titles end with " pab"
    if lower.endswith(" pab"):
        return "AB"
    for keyword, code in config.DOC_TYPE_MAP.items():
        if keyword in lower:
            return code
    return "UNKNOWN"


def _parse_section_year_series(heading_text: str) -> tuple[int | None, str | None]:
    """Parse year and series from an h4 section heading like '2024 - June series'."""
    m = re.search(
        r"\b(20\d{2})\b.*\b(january|february|march|april|may|june|july|august|"
        r"september|october|november|december)\b",
        heading_text, re.IGNORECASE,
    )
    if m:
        return int(m.group(1)), m.group(2).lower()
    # Year only
    m2 = re.search(r"\b(20\d{2})\b", heading_text)
    if m2:
        return int(m2.group(1)), None
    return None, None


def _parse_component(unit_code_text: str) -> str | None:
    """Extract component number from unit-code span, e.g. 'H640/01' → '01'."""
    m = re.search(r"/\s*(\d+[A-Za-z]?)\s*$", unit_code_text.strip())
    return m.group(1) if m else None


def _parse_file_size_kb(meta_text: str) -> float | None:
    m = re.search(r"([\d.]+)\s*KB", meta_text, re.IGNORECASE)
    if m:
        return float(m.group(1))
    m2 = re.search(r"([\d.]+)\s*MB", meta_text, re.IGNORECASE)
    if m2:
        return round(float(m2.group(1)) * 1024, 2)
    return None


_DOC_TYPE_SLUGS = (
    "question-paper-",
    "mark-scheme-",
    "examiners-report-",
    "examiner-s-report-",
)


def _parse_paper_name(filename: str) -> str | None:
    """Extract paper name from filename.

    Filenames follow the pattern:
        {id}-{doc-type}-{paper-name}[-answer-booklet|-pab].pdf

    Returns None for answer booklets and PABs.
    """
    stem = re.sub(r"\.pdf$", "", filename, flags=re.IGNORECASE)
    stem = re.sub(r"^\d+-", "", stem)

    if stem.endswith("-answer-booklet") or stem.endswith("-answer-book") or stem.endswith("-pab"):
        return None

    for slug in _DOC_TYPE_SLUGS:
        if stem.startswith(slug):
            name = stem[len(slug):]
            return name.replace("-", " ").title() if name else None

    return None


def parse_resources_html(html: str) -> list[dict]:
    """Extract PDF resource items from OCR filter response HTML.

    The HTML is structured as nested accordions:
      h4.level-2.heading  →  "2024 - June series"
        ul.resource-list
          li.resource
            a[href=*.pdf]  title text
            span.unit-code  e.g. H640/01
            span.file-meta-info  e.g. - PDF 2MB

    Returns a list of dicts: {title, url, filename, year, series, paper_number, file_size_kb}.
    """
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen_urls: set[str] = set()

    for h4 in soup.find_all("h4", class_="level-2"):
        heading_text = h4.get_text(strip=True)
        year, series = _parse_section_year_series(heading_text)

        # The resources are in the next sibling div.level-2.accordion-content
        content_div = h4.find_next_sibling("div", class_="level-2")
        if not content_div:
            continue

        for li in content_div.find_all("li", class_="resource"):
            a = li.find("a", href=True)
            if not a or ".pdf" not in a["href"].lower():
                continue

            href = a["href"]
            url = href if href.startswith("http") else config.BASE_URL + href
            if url in seen_urls:
                continue
            seen_urls.add(url)

            title = a.get_text(strip=True)
            filename = url.split("/")[-1].split("?")[0]

            unit_span = li.find("span", class_="unit-code")
            paper_number = _parse_component(unit_span.get_text()) if unit_span else None

            meta_span = li.find("span", class_="file-meta-info")
            file_size_kb = _parse_file_size_kb(meta_span.get_text()) if meta_span else None

            items.append({
                "title": title,
                "url": url,
                "filename": filename,
                "year": year,
                "series": series,
                "paper_number": paper_number,
                "file_size_kb": file_size_kb,
            })

    return items


# ---------------------------------------------------------------------------
# Entry building
# ---------------------------------------------------------------------------

def build_entry(item: dict, spec_code: str, spec_config: dict) -> dict | None:
    """Convert a raw resource item into a PastPaper-compatible dict.

    Returns None for non-QP/MS types or future years.
    """
    title = item["title"]
    url = item["url"]
    filename = item["filename"]
    year = item["year"]
    series = item["series"]

    paper_type = _parse_doc_type(title)
    if paper_type not in config.KEEP_TYPES:
        return None

    if year is not None and year > config.MAX_YEAR:
        return None

    paper_number = item["paper_number"]
    paper_name = _parse_paper_name(filename)

    content_id = f"ocr:{spec_code}:{filename}"
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
        "tier": None,
        "filename": filename,
        "local_path": local_path,
        "source_url": url,
        "file_size_kb": item.get("file_size_kb"),
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
) -> list[dict]:
    """Fetch, parse, and optionally download all papers for one spec."""
    if session is None:
        session = make_session()

    spec_config = config.SPECS[spec_code]
    qual_value = spec_config["qualification_value"]
    level = spec_config["level"]
    page_id = spec_config.get("page_id", "")

    print(f"\n{'='*60}")
    print(f"Scraping {spec_code}: {spec_config['subject']}")
    print(f"  qualification_value={qual_value}  level={level!r}")

    
    print("  Fetching available levels...")
    try:
        levels = fetch_levels(qual_value, session)
        if levels:
            print(f"  Available levels: {levels}")
            if level not in levels:
                print(f"  WARNING: configured level {level!r} not in available levels {levels}")
        time.sleep(config.PAGE_DELAY_S)
    except Exception as exc:
        print(f"  WARNING: getlevels failed ({exc}) — proceeding anyway")

    
    print("  Fetching resource list (this may take ~10 s)...")
    html = fetch_resources_html(qual_value, level, page_id, session)
    print(f"  Response HTML length: {len(html)} chars")

    
    raw_items = parse_resources_html(html)
    print(f"  PDF links found: {len(raw_items)}")

    entries: list[dict] = []
    downloaded = 0
    skipped = 0
    errors = 0

    for item in raw_items:
        entry = build_entry(item, spec_code, spec_config)
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
# Index helpers
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
    parser = argparse.ArgumentParser(description="Scrape OCR past papers via resource filter API")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--spec-code", help="Single spec code to scrape (e.g. H640)")
    group.add_argument("--all", dest="all_specs", action="store_true",
                       help="Scrape all configured specs")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print discovered entries without writing anything")
    parser.add_argument("--download", action="store_true",
                        help="Download PDFs (default: index metadata only)")
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

    session = make_session()
    session.headers.update({"User-Agent": "TopicTracker/1.0 Educational"})

    for spec_code in specs_to_scrape:
        try:
            entries = scrape_spec(
                spec_code,
                dry_run=args.dry_run,
                download=args.download,
                session=session,
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
