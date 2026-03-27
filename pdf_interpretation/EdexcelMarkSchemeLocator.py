"""
Locate mark scheme sections for each question in an Edexcel mark scheme PDF.

Scans for question boundaries in the mark scheme table structure and maps
each question number to its start/end page and y coordinates, so the frontend
can crop and display the relevant section.
"""

import re
import fitz
import logging

logger = logging.getLogger(__name__)

END_MARGIN = 10

# Maximum x-coordinate for the Question column
Q_COLUMN_MAX_X_ALEVEL = 100
Q_COLUMN_MAX_X_GCSE = 90


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

    Edexcel mark schemes have several pages of general guidance before the
    actual question-by-question marking. Look for table headers that signal
    the start of the mark scheme content.
    """
    for i, ln in enumerate(lines):
        text = ln["text"].strip()
        # A-level: "Question | Scheme | Marks" table header
        if text == "Question" and i + 1 < len(lines):
            next_text = lines[i + 1]["text"].strip()
            if next_text in ("Scheme", "Answer"):
                return i
        # GCSE: "Paper: XXXX" header followed by column headers
        if re.match(r'^Paper:', text):
            return i
    return 0


def _detect_format(lines: list[dict], start_idx: int) -> str:
    """Detect A-level vs GCSE format based on table column headers."""
    for ln in lines[start_idx:start_idx + 20]:
        text = ln["text"].strip()
        if text == "Scheme":
            return "alevel"
        if text == "Additional guidance" or text == "Mark scheme":
            return "gcse"
    return "alevel"


def _locate_alevel(lines: list[dict], start_idx: int, questions: list[dict],
                   page_heights: list[float], doc) -> list[dict]:
    """
    Locate questions in A-level Edexcel mark schemes.

    A-level Edexcel mark schemes have a table with columns:
    Question | Scheme | Marks | AOs

    Question identifiers appear as "1", "2(a)", "3", "9(a)", "14(a)" etc.
    at x < 100 in the Question column.
    "(N marks)" appears at the end of each question's mark scheme.
    """
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

    # Patterns for question identifiers in the Question column
    # "1", "2(a)", "9(a)", "14(a)", "4 (a)" — top-level question start
    q_start_re = re.compile(r'^(\d+)\s*(?:\([a-z]\))?$')
    # "(N marks)" total marker
    total_marks_re = re.compile(r'^\((\d+)\s+marks?\)$')

    # Track question start positions and total-marks end positions
    q_positions: dict[int, tuple[int, float]] = {}  # num -> (page, y_top)
    q_totals: dict[int, tuple[int, float]] = {}     # num -> (page, y_bottom)

    # Find "Question" table header positions on each page
    table_header_pages: dict[int, float] = {}  # page -> header y_top
    for ln in lines[start_idx:]:
        if ln["text"].strip() == "Question" and ln["x_left"] < Q_COLUMN_MAX_X_ALEVEL:
            table_header_pages[ln["page"]] = ln["y_top"]

    # Track which question we're currently inside
    current_q = None
    # After "(N marks)", we're in the notes section until next table header
    in_table = True
    last_table_page = -1

    for i, ln in enumerate(lines):
        if i < start_idx:
            continue

        text = ln["text"].strip()

        # Re-enter table mode when we hit a new page with a "Question" header
        if ln["page"] in table_header_pages and ln["page"] != last_table_page:
            in_table = True
            last_table_page = ln["page"]

        # Check for "(N marks)" total line — marks end of current question
        mt = total_marks_re.match(text)
        if mt and current_q is not None:
            q_totals[current_q] = (ln["page"], ln["y_bottom"])
            in_table = False  # notes section follows
            continue

        if not in_table:
            continue

        # Only consider Question column items on table pages
        if ln["x_left"] > Q_COLUMN_MAX_X_ALEVEL:
            continue
        if ln["page"] not in table_header_pages:
            continue

        # Skip footer/header noise near edges of page
        if ln["y_top"] > page_heights[ln["page"]] - 40:
            continue

        # Check for question start
        m = q_start_re.match(text)
        if m:
            num = int(m.group(1))
            if num in wanted_nums and num not in q_positions:
                q_positions[num] = (ln["page"], ln["y_top"])
            current_q = num

    return _build_results(q_positions, q_totals, questions, page_heights, doc)


def _locate_gcse(lines: list[dict], start_idx: int, questions: list[dict],
                 page_heights: list[float], doc) -> list[dict]:
    """
    Locate questions in GCSE Edexcel mark schemes.

    GCSE Edexcel mark schemes have a table with columns:
    Question | Answer | Mark | Mark scheme | Additional guidance

    Question numbers appear as standalone digits at x < 90 in the
    Question column. Each new question number starts a new row.
    """
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

    q_positions: dict[int, tuple[int, float]] = {}
    standalone_re = re.compile(r'^(\d+)$')

    for i, ln in enumerate(lines):
        if i < start_idx:
            continue

        if ln["x_left"] > Q_COLUMN_MAX_X_GCSE:
            continue

        # Skip footer/header noise
        if ln["y_top"] > page_heights[ln["page"]] - 40:
            continue

        text = ln["text"].strip()

        m = standalone_re.match(text)
        if m:
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

        # End boundary: prefer total marks line if available,
        # otherwise fall back to next question's start
        if num in q_totals:
            end_page, end_y = q_totals[num]
            end_y += END_MARGIN
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

    logger.info("Edexcel mark scheme format: %s, content starts at line %d", fmt, start_idx)

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
