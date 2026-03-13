"""
Locate mark scheme sections for each question in an AQA mark scheme PDF.

Scans for question boundaries in the mark scheme table structure and maps
each question number to its start/end page and y coordinates, so the frontend
can crop and display the relevant section.
"""

import re
import fitz
import logging

logger = logging.getLogger(__name__)

END_MARGIN = 10

# Maximum x-coordinate for the Q column (leftmost table column)
Q_COLUMN_MAX_X = 70


def _extract_lines(doc) -> tuple[list[dict], list[float]]:
    """Extract all text lines with positions from the PDF."""
    lines: list[dict] = []
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
                        "x_left": line["bbox"][0],
                        "y_top": line["bbox"][1],
                        "y_bottom": line["bbox"][3],
                        "text": text,
                    })

    return lines, page_heights


def _find_content_start(lines: list[dict]) -> int:
    """
    Find the first line index where actual mark scheme content begins.
    Look for the first question identifier (Q1, Question 1, or 01.1).
    """
    for i, ln in enumerate(lines):
        text = ln["text"].strip()
        if "total" in text.lower():
            continue
        if re.match(r'^Q\s*1\b', text):
            return i
        if re.match(r'^Question\s+1\b', text, re.IGNORECASE):
            return i
        if re.match(r'^0?1\.1\b', text):
            return i
    return 0


def _detect_format(lines: list[dict], start_idx: int) -> str:
    """Detect A-level vs GCSE format."""
    for ln in lines[start_idx:start_idx + 50]:
        text = ln["text"].strip()
        if re.match(r'^Question\s+\d+', text, re.IGNORECASE) and "total" not in text.lower():
            return "gcse"
    return "alevel"


def _locate_alevel(lines: list[dict], start_idx: int, questions: list[dict],
                   page_heights: list[float], doc) -> list[dict]:
    """
    Locate questions in A-level AQA mark schemes.

    A-level AQA mark schemes have a table with Q column at the left margin.
    Question identifiers appear as "Q1", "Q2", or just "3", "4" at x < 65.
    Sub-parts appear as "5(a)", "6(b)" etc.
    """
    # Group input questions by top-level number
    groups: dict[int, list[dict]] = {}
    for q in questions:
        m = re.match(r'^(\d+)', q["id"])
        if not m:
            continue
        num = int(m.group(1))
        groups.setdefault(num, []).append(q)

    wanted_nums = set(groups.keys())
    if not wanted_nums:
        return []

    # Scan lines in Q column (x < Q_COLUMN_MAX_X) for question markers
    q_positions: dict[int, tuple[int, float]] = {}  # num -> (page, y_top)
    # Track "Q" table header positions so we can start from the header row
    q_headers: list[tuple[int, float]] = []  # [(page, y_top), ...]
    # Track "Question N Total" positions for end boundaries
    q_totals: dict[int, tuple[int, float]] = {}  # num -> (page, y_bottom)

    # Patterns for question identifiers in the Q column
    explicit_q_re = re.compile(r'^Q\s*(\d+)')          # Q1, Q2
    subpart_re = re.compile(r'^(\d+)\s*\([a-z]\)')     # 5(a), 6(b)
    standalone_re = re.compile(r'^(\d+)\s*$')           # just "3", "4"
    q_total_re = re.compile(r'^Question\s+(\d+)\s+Total', re.IGNORECASE)

    last_found_num = 0

    for i, ln in enumerate(lines):
        if i < start_idx:
            continue

        # Check for "Question N Total" lines (these can be wider than Q column)
        mt = q_total_re.match(ln["text"].strip())
        if mt:
            num = int(mt.group(1))
            q_totals[num] = (ln["page"], ln["y_bottom"])
            continue

        # Only consider Q column items
        if ln["x_left"] > Q_COLUMN_MAX_X:
            continue

        # Skip footer page numbers (near bottom of page)
        if ln["y_top"] > page_heights[ln["page"]] - 60:
            continue

        text = ln["text"].strip()

        # Track "Q" table column headers
        if text == "Q":
            q_headers.append((ln["page"], ln["y_top"]))
            continue

        # Check for "Total" markers
        if re.match(r'^Total\b', text, re.IGNORECASE):
            continue

        # Explicit Q\d+ always matches
        m = explicit_q_re.match(text)
        if m:
            num = int(m.group(1))
            if num in wanted_nums and num not in q_positions:
                q_positions[num] = (ln["page"], ln["y_top"])
                last_found_num = max(last_found_num, num)
            continue

        # Sub-part like "5(a)" — record as the parent question
        m = subpart_re.match(text)
        if m:
            num = int(m.group(1))
            if num in wanted_nums and num not in q_positions:
                q_positions[num] = (ln["page"], ln["y_top"])
                last_found_num = max(last_found_num, num)
            continue

        # Standalone number — only accept if it's sequentially after previous
        m = standalone_re.match(text)
        if m:
            num = int(m.group(1))
            if (num in wanted_nums and num not in q_positions
                    and num > last_found_num):
                q_positions[num] = (ln["page"], ln["y_top"])
                last_found_num = num

    # Adjust start positions: use the nearest preceding "Q" table header
    for num in q_positions:
        q_page, q_y = q_positions[num]
        best_header = None
        for h_page, h_y in q_headers:
            if (h_page < q_page) or (h_page == q_page and h_y < q_y):
                if best_header is None:
                    best_header = (h_page, h_y)
                elif (h_page > best_header[0]) or (h_page == best_header[0] and h_y > best_header[1]):
                    best_header = (h_page, h_y)
        if best_header:
            q_positions[num] = best_header

    return _build_results(q_positions, q_totals, questions, page_heights, doc)


def _locate_gcse(lines: list[dict], start_idx: int, questions: list[dict],
                 page_heights: list[float], doc) -> list[dict]:
    """
    Locate questions in GCSE AQA mark schemes.
    Uses "Question N" section headers.
    """
    q_header_re = re.compile(r'^Question\s+(\d+)', re.IGNORECASE)
    q_positions: dict[int, tuple[int, float]] = {}

    groups: dict[int, list[dict]] = {}
    for q in questions:
        m = re.match(r'^(\d+)', q["id"])
        if not m:
            continue
        num = int(m.group(1))
        groups.setdefault(num, []).append(q)

    wanted_nums = set(groups.keys())

    for i, ln in enumerate(lines):
        if i < start_idx:
            continue
        m = q_header_re.match(ln["text"])
        if m and "total" not in ln["text"].lower():
            num = int(m.group(1))
            if num in wanted_nums and num not in q_positions:
                q_positions[num] = (ln["page"], ln["y_top"])

    return _build_results(q_positions, {}, questions, page_heights, doc)


def _build_results(q_positions: dict[int, tuple[int, float]],
                   q_totals: dict[int, tuple[int, float]],
                   questions: list[dict], page_heights: list[float],
                   doc) -> list[dict]:
    """Build location results from question positions."""
    if not q_positions:
        return []

    sorted_nums = sorted(q_positions.keys(),
                         key=lambda n: (q_positions[n][0], q_positions[n][1]))

    results = []
    for q in questions:
        m = re.match(r'^(\d+)', q["id"])
        if not m:
            continue
        num = int(m.group(1))
        if num not in q_positions:
            continue

        start_page, start_y = q_positions[num]

        # End boundary: prefer "Question N Total" line if available,
        # otherwise fall back to next question's start
        if num in q_totals:
            end_page, end_y = q_totals[num]
            end_y += END_MARGIN  # small margin below the total row
        elif sorted_nums.index(num) + 1 < len(sorted_nums):
            next_num = sorted_nums[sorted_nums.index(num) + 1]
            end_page, end_y = q_positions[next_num]
            end_y = max(0, end_y - END_MARGIN)
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


def locate_mark_scheme_questions(
    ms_pdf_path: str,
    questions: list[dict],
) -> list[dict]:
    """
    Locate each question's mark scheme section in the PDF.

    Args:
        ms_pdf_path: Path to the mark scheme PDF file.
        questions: List of dicts with 'id' key (question number, e.g. '1', '1a', '2.1').

    Returns:
        List of dicts with keys: question_id, start_page, start_y, end_page, end_y.
        Returns empty list if location fails.
    """
    try:
        doc = fitz.open(ms_pdf_path)
    except Exception as e:
        logger.warning("Failed to open mark scheme PDF: %s", e)
        return []

    if doc.page_count == 0:
        doc.close()
        return []

    lines, page_heights = _extract_lines(doc)

    if not lines:
        doc.close()
        return []

    start_idx = _find_content_start(lines)
    fmt = _detect_format(lines, start_idx)

    logger.info("Mark scheme format: %s, content starts at line %d", fmt, start_idx)

    if fmt == "gcse":
        results = _locate_gcse(lines, start_idx, questions, page_heights, doc)
    else:
        results = _locate_alevel(lines, start_idx, questions, page_heights, doc)

    doc.close()

    if results:
        logger.info("Located %d mark scheme sections", len(results))
    else:
        logger.info("Could not locate any mark scheme sections")

    return results
