import re
import logging
from typing import List, Dict, Optional, Callable, Tuple

logger = logging.getLogger(__name__)

# Roman numeral values for sorting sub-parts like (i), (ii), (iii)
_ROMAN_ORDER = {
    'i': 1, 'ii': 2, 'iii': 3, 'iv': 4, 'v': 5,
    'vi': 6, 'vii': 7, 'viii': 8, 'ix': 9, 'x': 10,
    'xi': 11, 'xii': 12,
}


def _question_sort_key(q):
    """Natural sort key for question IDs like '1', '1a', '1b(i)', '10a'."""
    qid = q["id"]
    m = re.match(r'(\d+)(.*)', qid)
    if not m:
        return (0, qid, 0)
    num = int(m.group(1))
    rest = m.group(2)
    m2 = re.match(r'([a-z]?)(?:\(([^)]*)\))?', rest)
    part_letter = m2.group(1) if m2 and m2.group(1) else ''
    sub_part = m2.group(2) if m2 and m2.group(2) else ''
    sub_num = _ROMAN_ORDER.get(sub_part, 0)
    return (num, part_letter, sub_num)


def sort_questions(questions: List[Dict]) -> List[Dict]:
    """Sort questions by their ID in natural exam order."""
    return sorted(questions, key=_question_sort_key)


def parse_exam_markdown(file_path: str, on_status: Optional[Callable[[str], None]] = None) -> Tuple[List[Dict], str]:
    """
    Parse an exam Markdown file into structured questions.
    Tries the LLM parser first, falls back to regex on failure.

    Returns a tuple of (questions, parser_name) where parser_name is "llm" or "regex".
    questions is a list of dicts:
      {
        "id": "2a(i)",
        "marks": 3,
        "text": "Full question text"
      }
    """
    # Try LLM-based parsing first
    try:
        from pdf_interpretation.llmParser import parse_with_llm
        results = parse_with_llm(file_path, on_status=on_status)
        results = sort_questions(results)
        logger.info("LLM parser succeeded for %s (%d questions)", file_path, len(results))
        return results, "llm"
    except Exception as e:
        logger.warning("LLM parser failed for %s: %s — falling back to regex", file_path, e)

    # Fallback to regex parser
    if on_status:
        on_status("LLM parser failed. Falling back to regex parser...")
    from pdf_interpretation.regexParser import parse_exam_markdown_regex
    return sort_questions(parse_exam_markdown_regex(file_path)), "regex"


def merge_questions(
    pymupdf_qs: List[Dict],
    olmocr_qs: List[Dict],
) -> List[Dict]:
    """
    Merge two question lists: take **text** from olmOCR (better math rendering)
    and **marks** from PyMuPDF (more reliable mark detection).

    Matching is by question ID. Any questions only present in one source
    are kept as-is. PyMuPDF-only questions are appended at the end.
    """
    pymupdf_by_id: Dict[str, Dict] = {q["id"]: q for q in pymupdf_qs}
    olmocr_by_id: Dict[str, Dict] = {q["id"]: q for q in olmocr_qs}

    merged: List[Dict] = []
    seen_ids: set = set()

    # Walk olmOCR list first (preserves its ordering)
    for q in olmocr_qs:
        qid = q["id"]
        seen_ids.add(qid)
        pymupdf_match = pymupdf_by_id.get(qid)
        merged.append({
            "id": qid,
            "text": q["text"],
            "marks": pymupdf_match["marks"] if pymupdf_match else q["marks"],
        })

    # Append any PyMuPDF-only questions
    for q in pymupdf_qs:
        if q["id"] not in seen_ids:
            merged.append(q)

    merged = sort_questions(merged)
    logger.info(
        "merge_questions: olmOCR=%d, PyMuPDF=%d, merged=%d",
        len(olmocr_qs), len(pymupdf_qs), len(merged),
    )
    return merged
