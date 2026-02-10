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
