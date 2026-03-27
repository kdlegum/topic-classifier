"""
Dispatch mark scheme location to the appropriate exam-board-specific locator.
"""

from pdf_interpretation.AQAmarkSchemeLocator import (
    locate_mark_scheme_questions as _aqa_locate,
)
from pdf_interpretation.EdexcelMarkSchemeLocator import (
    locate_mark_scheme_questions as _edexcel_locate,
)

_LOCATORS = {
    "AQA": _aqa_locate,
    "Edexcel": _edexcel_locate,
}


def locate_mark_scheme_questions(
    ms_pdf_path: str,
    questions: list[dict],
    exam_board: str = "",
) -> list[dict]:
    """
    Locate each question's mark scheme section in the PDF.

    Delegates to the appropriate exam-board-specific locator.
    Falls back to AQA locator for unknown boards.
    """
    locator = _LOCATORS.get(exam_board, _aqa_locate)
    return locator(ms_pdf_path, questions)
