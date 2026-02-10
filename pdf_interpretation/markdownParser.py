import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


def parse_exam_markdown(file_path: str) -> List[Dict]:
    """
    Parse an exam Markdown file into structured questions.
    Tries the LLM parser first, falls back to regex on failure.

    Returns a list of dicts:
      {
        "id": "2a(i)",
        "marks": 3,
        "text": "Full question text"
      }
    """
    # Try LLM-based parsing first
    try:
        from pdf_interpretation.llmParser import parse_with_llm
        results = parse_with_llm(file_path)
        logger.info("LLM parser succeeded for %s (%d questions)", file_path, len(results))
        return results
    except Exception as e:
        logger.warning("LLM parser failed for %s: %s — falling back to regex", file_path, e)

    # Fallback to regex parser
    from pdf_interpretation.regexParser import parse_exam_markdown_regex
    return parse_exam_markdown_regex(file_path)


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

    logger.info(
        "merge_questions: olmOCR=%d, PyMuPDF=%d, merged=%d",
        len(olmocr_qs), len(pymupdf_qs), len(merged),
    )
    return merged
