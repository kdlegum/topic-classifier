"""
Locate question positions in a PDF using PyMuPDF.

For each question, determines:
  - start_page, start_y: where the question header begins
  - end_page, end_y: bottom of the question content (start of next question minus margin)

Primary method: scan PDF text blocks for question number matches, verify with question text.
Backup method: use olmOCR JSONL page spans to map questions to pages.
"""

import re
import json
import fitz
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Margin in PDF points to subtract from the next question's start y
END_MARGIN = 15


def _normalize(text: str) -> str:
    """Lowercase and collapse non-alphanumeric to spaces."""
    return re.sub(r'[^a-z0-9\s]', ' ', text.lower()).strip()


def _extract_keywords(text: str, max_words: int = 8) -> set[str]:
    """Extract first N non-trivial words from text for matching."""
    STOP = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'of', 'in', 'to',
        'for', 'and', 'or', 'that', 'this', 'it', 'on', 'at', 'by', 'with',
    }
    words = _normalize(text).split()
    result = []
    for w in words:
        if len(w) > 1 and w not in STOP:
            result.append(w)
            if len(result) >= max_words:
                break
    return set(result)


def _find_paper_end(lines: list[dict], last_q_pos: tuple[int, float]) -> tuple[int, float] | None:
    """
    Find end-of-paper markers after the last question start.

    Scans for:
      - "END OF QUESTION PAPER" / "END OF QUESTIONS"
      - "TOTAL FOR [THIS] PAPER" marks line
      - Standalone total marks (number >= 30) on a line by itself

    Returns (page, y_bottom) or None.
    """
    last_page, last_y = last_q_pos

    end_marker_re = re.compile(r'END\s+OF\s+QUESTION', re.IGNORECASE)
    total_paper_re = re.compile(
        r'TOTAL\s+(?:FOR\s+)?(?:THIS\s+)?(?:PAPER|QUESTION\s*PAPER)',
        re.IGNORECASE,
    )
    standalone_re = re.compile(
        r'^\s*\[?\s*(\d+)\s*(?:marks?)?\s*\]?\s*$', re.IGNORECASE
    )

    # Forward scan for explicit end markers
    for ln in lines:
        if (ln["page"], ln["y_top"]) <= (last_page, last_y):
            continue
        if end_marker_re.search(ln["text"]):
            return (ln["page"], ln["y_bottom"])
        if total_paper_re.search(ln["text"]):
            return (ln["page"], ln["y_bottom"])

    # Backward scan for standalone total marks (>=30) after last question
    for ln in reversed(lines):
        if (ln["page"], ln["y_top"]) <= (last_page, last_y):
            break
        m = standalone_re.match(ln["text"])
        if m and int(m.group(1)) >= 30:
            return (ln["page"], ln["y_bottom"])

    return None


def _locate_via_pymupdf(doc, questions: list[dict]) -> list[dict]:
    """
    Primary locator: scan PDF text blocks with PyMuPDF.

    For each top-level question number, find the line that starts with it
    and verify using word overlap with the question text. Sub-parts (e.g. 1a, 1b)
    share the parent question's location.
    """
    # Build a flat list of text lines with positions
    lines: list[dict] = []  # {page, y_top, y_bottom, text}
    page_heights: list[float] = []

    for pn in range(doc.page_count):
        page = doc[pn]
        page_heights.append(page.rect.height)
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if b["type"] != 0:
                continue
            for line in b["lines"]:
                text = "".join(s["text"] for s in line["spans"]).strip()
                if text:
                    lines.append({
                        "page": pn,
                        "y_top": line["bbox"][1],
                        "y_bottom": line["bbox"][3],
                        "text": text,
                    })

    if not lines:
        logger.info("No text blocks found in PDF (possibly scanned)")
        return []

    # Detect AQA format: question IDs use dot notation like "1.1", "2.3"
    is_aqa = any('.' in q["id"] for q in questions)

    # Group input questions by top-level number
    groups: dict[int, list[dict]] = {}
    for q in questions:
        m = re.match(r'^(\d+)', q["id"])
        if not m:
            continue
        num = int(m.group(1))
        groups.setdefault(num, []).append(q)

    # Find start position for each top-level question number
    starts: dict[int, tuple[int, float]] = {}  # num -> (page, y_top)

    for num, qs in groups.items():
        if is_aqa:
            # AQA PDFs: top-level question markers appear as standalone "0 N" lines
            # (the leading zero is from the two-digit box format: [0][N]).
            # Use exact-end match so "0 1 . 2" sub-part lines don't match as Q1.
            # Fall back to prefix match if no standalone markers found.
            pattern = re.compile(rf'^0\s+{num}\s*$')
        else:
            # Standard format (OCR, Edexcel): question number at start of line
            pattern = re.compile(rf'^[Qq]?\s*{num}(?!\d)')

        candidates: list[tuple[int, int, float]] = []  # (line_idx, page, y_top)
        for i, ln in enumerate(lines):
            if pattern.match(ln["text"]):
                candidates.append((i, ln["page"], ln["y_top"]))

        # AQA fallback: if no standalone "0 N" found, try prefix match "0 N ..."
        if not candidates and is_aqa:
            fallback = re.compile(rf'^0\s+{num}(?!\d)')
            for i, ln in enumerate(lines):
                if fallback.match(ln["text"]):
                    candidates.append((i, ln["page"], ln["y_top"]))

        if not candidates:
            continue

        if len(candidates) == 1:
            starts[num] = (candidates[0][1], candidates[0][2])
        else:
            # Multiple candidates — use text overlap to pick the best match
            ref_text = qs[0].get("text", "")
            ref_words = _extract_keywords(ref_text)

            best_idx = 0
            best_score = -1

            for ci, (line_idx, pg, yt) in enumerate(candidates):
                # Build a text window: this line + next ~5 lines
                window_texts = [
                    lines[j]["text"]
                    for j in range(line_idx, min(line_idx + 6, len(lines)))
                ]
                window = " ".join(window_texts)
                window_words = set(_normalize(window).split())

                score = len(ref_words & window_words) if ref_words else 0
                if score > best_score:
                    best_score = score
                    best_idx = ci

            _, pg, yt = candidates[best_idx]
            starts[num] = (pg, yt)

    if not starts:
        logger.info("Could not locate any question starts in PDF")
        return []

    # Sort question numbers by their position in the document
    sorted_nums = sorted(starts.keys(), key=lambda n: (starts[n][0], starts[n][1]))

    # Try to find where the paper content actually ends (before formula booklet etc.)
    paper_end = _find_paper_end(lines, starts[sorted_nums[-1]])

    # Build results — map each input question to its parent question's region
    results = []

    for q in questions:
        m = re.match(r'^(\d+)', q["id"])
        if not m:
            continue
        num = int(m.group(1))
        if num not in starts:
            continue

        start_page, start_y = starts[num]

        # End = next question's start minus margin
        idx = sorted_nums.index(num)
        if idx + 1 < len(sorted_nums):
            next_num = sorted_nums[idx + 1]
            end_page, end_y = starts[next_num]
            end_y = max(0, end_y - END_MARGIN)
        else:
            # Last question — use paper end marker if found, else full last page
            if paper_end:
                end_page, end_y = paper_end
            else:
                end_page = doc.page_count - 1
                end_y = page_heights[end_page] - 30

        results.append({
            "question_id": q["id"],
            "start_page": start_page,
            "start_y": round(start_y, 1),
            "end_page": end_page,
            "end_y": round(end_y, 1),
        })

    return results


def _locate_via_olmocr_jsonl(workspace_path: str, questions: list[dict]) -> list[dict]:
    """
    Backup locator: use olmOCR JSONL page spans.

    The JSONL attributes contain pdf_page_numbers: [[start_char, end_char, page_num], ...]
    which maps character positions in the extracted text to PDF page numbers.
    We find each question's text in the full text and map it to a page.
    """
    workspace = Path(workspace_path)
    results_dir = workspace / "results"
    if not results_dir.exists():
        logger.info("No olmOCR results directory at %s", results_dir)
        return []

    # Find the JSONL file
    jsonl_files = list(results_dir.glob("output_*.jsonl"))
    if not jsonl_files:
        logger.info("No JSONL files found in %s", results_dir)
        return []

    # Parse the first (and typically only) JSONL file
    jsonl_path = jsonl_files[0]
    try:
        with open(jsonl_path, "r", encoding="utf-8") as f:
            record = json.loads(f.readline())
    except Exception as e:
        logger.warning("Failed to parse olmOCR JSONL %s: %s", jsonl_path, e)
        return []

    full_text = record.get("text", "")
    page_spans = record.get("attributes", {}).get("pdf_page_numbers", [])

    if not full_text or not page_spans:
        logger.info("olmOCR JSONL missing text or page spans")
        return []

    def char_to_page(pos: int) -> int | None:
        for start, end, page_num in page_spans:
            if start <= pos < end:
                return page_num
        return None

    # Group questions by top-level number to find page ranges
    groups: dict[int, list[dict]] = {}
    for q in questions:
        m = re.match(r'^(\d+)', q["id"])
        if not m:
            continue
        num = int(m.group(1))
        groups.setdefault(num, []).append(q)

    # For each top-level question, find its text position and page
    starts: dict[int, int] = {}  # num -> page_number (0-indexed)
    sorted_nums_list: list[int] = sorted(groups.keys())

    for num in sorted_nums_list:
        qs = groups[num]
        ref_text = qs[0].get("text", "")
        # Try finding a snippet of the question text
        for length in (60, 30, 15):
            snippet = ref_text[:length].strip()
            if not snippet:
                continue
            pos = full_text.find(snippet)
            if pos != -1:
                page = char_to_page(pos)
                if page is not None:
                    starts[num] = page
                    break

    if not starts:
        logger.info("olmOCR JSONL: could not map any questions to pages")
        return []

    # Build results — page-level only (no y precision)
    total_pages = record.get("metadata", {}).get("pdf-total-pages", max(starts.values()) + 1)
    sorted_nums = sorted(starts.keys())

    results = []
    for q in questions:
        m = re.match(r'^(\d+)', q["id"])
        if not m:
            continue
        num = int(m.group(1))
        if num not in starts:
            continue

        start_page = starts[num]
        idx = sorted_nums.index(num)

        if idx + 1 < len(sorted_nums):
            next_page = starts[sorted_nums[idx + 1]]
            if next_page == start_page:
                # Same page — can't distinguish, show full page
                end_page = start_page
            else:
                end_page = next_page - 1
        else:
            end_page = total_pages - 1

        results.append({
            "question_id": q["id"],
            "start_page": start_page,
            "start_y": 0.0,
            "end_page": end_page,
            "end_y": 0.0,  # 0 signals "full page" — frontend can handle this
        })

    return results


def _get_last_content_page_from_olmocr(workspace_path: str, questions: list[dict]) -> int | None:
    """
    Use olmOCR JSONL to find the last PDF page containing question content.

    Looks for end-of-paper markers first, then falls back to the page of
    the last question's text.

    Returns 0-indexed page number, or None.
    """
    workspace = Path(workspace_path)
    results_dir = workspace / "results"
    if not results_dir.exists():
        return None

    jsonl_files = list(results_dir.glob("output_*.jsonl"))
    if not jsonl_files:
        return None

    try:
        with open(jsonl_files[0], "r", encoding="utf-8") as f:
            record = json.loads(f.readline())
    except Exception:
        return None

    full_text = record.get("text", "")
    page_spans = record.get("attributes", {}).get("pdf_page_numbers", [])

    if not full_text or not page_spans:
        return None

    def char_to_page(pos: int) -> int | None:
        for start, end, page_num in page_spans:
            if start <= pos < end:
                return page_num
        return None

    # Look for end-of-paper markers in the OCR text
    for pattern in [
        re.compile(r'END\s+OF\s+QUESTION', re.IGNORECASE),
        re.compile(r'TOTAL\s+(?:FOR\s+)?(?:THIS\s+)?(?:PAPER|QUESTION\s*PAPER)', re.IGNORECASE),
    ]:
        m = pattern.search(full_text)
        if m:
            page = char_to_page(m.start())
            if page is not None:
                return page

    # Fall back: find the latest page containing any question's text
    latest_page = None
    for q in questions:
        text = q.get("text", "")
        for length in (60, 30, 15):
            snippet = text[:length].strip()
            if not snippet:
                continue
            pos = full_text.rfind(snippet)
            if pos != -1:
                page = char_to_page(pos)
                if page is not None and (latest_page is None or page > latest_page):
                    latest_page = page
                break

    return latest_page


def locate_questions_in_pdf(
    pdf_path: str,
    questions: list[dict],
    workspace_path: str | None = None,
) -> list[dict]:
    """
    Locate each question in the PDF.

    Args:
        pdf_path: Path to the PDF file.
        questions: List of question dicts with 'id' key (e.g. '1', '1a', '2a_i')
                   and 'text' key (the question text for verification).
        workspace_path: Optional path to olmOCR workspace for JSONL backup.

    Returns:
        List of dicts with keys: question_id, start_page, start_y, end_page, end_y.
        Returns empty list if location fails entirely.
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        logger.warning("Failed to open PDF for question location: %s", e)
        return []

    if doc.page_count == 0:
        doc.close()
        return []

    # Collect page heights for olmOCR capping
    page_heights = [doc[pn].rect.height for pn in range(doc.page_count)]

    # Primary: PyMuPDF text matching
    results = _locate_via_pymupdf(doc, questions)
    doc.close()

    if results:
        logger.info("Located %d questions via PyMuPDF", len(results))

        # Refine: use olmOCR JSONL to cap the last question's end page
        # (prevents showing formula booklet / blank pages after questions)
        if workspace_path:
            last_content_page = _get_last_content_page_from_olmocr(workspace_path, questions)
            if last_content_page is not None:
                for r in results:
                    if r["end_page"] > last_content_page:
                        r["end_page"] = last_content_page
                        r["end_y"] = round(page_heights[last_content_page] - 30, 1)
                logger.info("Capped end pages to %d via olmOCR", last_content_page)

        return results

    # Backup: olmOCR JSONL page mapping
    if workspace_path:
        results = _locate_via_olmocr_jsonl(workspace_path, questions)
        if results:
            logger.info("Located %d questions via olmOCR JSONL", len(results))
            return results

    logger.info("Could not locate questions in PDF by any method")
    return []
