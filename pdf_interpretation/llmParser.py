import re
import json
import logging
from typing import List, Dict, Optional, Callable

from google import genai
from google.genai import types
from google.genai.types import ThinkingConfig

# Schema for structured JSON output — forces Gemini to produce valid JSON
_QUESTION_SCHEMA = types.Schema(
    type="ARRAY",
    items=types.Schema(
        type="OBJECT",
        properties={
            "id": types.Schema(type="STRING"),
            "marks": types.Schema(type="INTEGER", nullable=True),
            "text": types.Schema(type="STRING"),
        },
        required=["id", "text"],
    ),
)

logger = logging.getLogger(__name__)

_client = None


def _get_client() -> genai.Client:
    """Lazy-load the Gemini API client as a singleton."""
    global _client
    if _client is None:
        _client = genai.Client()
    return _client


SYSTEM_PROMPT = """You extract exam questions from a markdown document into structured JSON.

You are given an entire exam paper in markdown format. Output a JSON array of every answerable question part.

Format — JSON array only, nothing else:
[{"id": "3a", "marks": 3, "text": "..."}, ...]

Rules:
- "id": question number + part letter + optional roman numeral. Examples: "3", "3a", "3b(i)", "3b(ii)". No "Q" prefix.
- "marks": integer from [N] brackets, or null if not shown.
- "text": full question text for that part. Prepend the stem/preamble if the subpart needs it for context. Keep LaTeX as-is. Keep [DIAGRAM] and [TABLE] placeholders.
- Include all multiple choice options (A, B, C, D, etc.) as part of the question text. Do NOT strip them.
- Use \\n line breaks in the text field to preserve structure (e.g. between the question stem and options).
- Remove mark brackets like [3] from the text field.
- If a question has no sub-parts, output a single item with just the question number as id.
- Output ONLY the JSON array. No commentary, no markdown fences."""

FEW_SHOT_USER = """1 A shop sells two types of coffee.

(a) Type A costs £3.50 per bag. Calculate the cost of 4 bags. [2]

(b) Type B costs £4.20 per bag.

(i) Calculate the cost of 3 bags of Type B. [2]

(ii) Find the total cost of 4 bags of Type A and 3 bags of Type B. [3]

2 Solve the equation 3x + 5 = 20. [3]

3 Which of the following is a prime number?
A 4
B 6
C 7
D 9
[1]"""

FEW_SHOT_RESPONSE = """[
  {"id": "1a", "marks": 2, "text": "A shop sells two types of coffee. Type A costs £3.50 per bag. Calculate the cost of 4 bags."},
  {"id": "1b(i)", "marks": 2, "text": "A shop sells two types of coffee. Type B costs £4.20 per bag. Calculate the cost of 3 bags of Type B."},
  {"id": "1b(ii)", "marks": 3, "text": "A shop sells two types of coffee. Type A costs £3.50 per bag. Type B costs £4.20 per bag. Find the total cost of 4 bags of Type A and 3 bags of Type B."},
  {"id": "2", "marks": 3, "text": "Solve the equation 3x + 5 = 20."},
  {"id": "3", "marks": 1, "text": "Which of the following is a prime number?\\nA 4\\nB 6\\nC 7\\nD 9"}
]"""

CONTINUE_PROMPT = (
    "Your previous response was truncated. Continue extracting the remaining "
    "questions from the exam paper. Output ONLY a JSON array of the remaining "
    "questions you have not yet output. Do not repeat any questions."
)

MODEL = "gemini-2.5-flash-lite"


def preprocess_markdown(text: str) -> str:
    """Strip exam boilerplate and normalize the markdown for LLM parsing."""
    # Remove boilerplate before the first question.
    # Require 1-3 digit number (avoids matching years like "2024") followed by
    # whitespace and actual content (avoids matching lone page numbers).
    first_q = re.search(r'(?m)^\d{1,3}\s+\S', text)
    if first_q and first_q.start() > 0:
        before = text[:first_q.start()].strip()
        # Only strip if the content before has no sub-part markers (i.e. is headers/instructions)
        if not re.search(r'\([a-z]\)', before):
            text = text[first_q.start():]

    # Remove content after "END OF QUESTION PAPER" or similar
    for marker in [r'END\s+OF\s+QUESTION\s+PAPER', r'END\s+OF\s+QUESTIONS']:
        match = re.search(marker, text, re.IGNORECASE)
        if match:
            text = text[:match.start()]

    # Replace images with [DIAGRAM]
    text = re.sub(r'!\[.*?\]\(.*?\)', '[DIAGRAM]', text)

    # Replace HTML tables with [TABLE]
    text = re.sub(r'<table\b[^>]*>.*?</table>', '[TABLE]', text, flags=re.IGNORECASE | re.DOTALL)

    # Normalize whitespace
    text = re.sub(r'\n{3,}', '\n\n', text.strip())

    return text


def validate_questions(questions: list) -> List[Dict]:
    """Validate and normalize parsed question dicts."""
    validated = []
    for q in questions:
        if not isinstance(q, dict):
            continue

        qid = q.get("id")
        marks = q.get("marks")
        text = q.get("text")

        if not isinstance(qid, str) or not qid.strip():
            continue

        # Normalize: strip leading Q/q
        qid = re.sub(r'^[Qq]\s*', '', qid.strip())
        if not qid:
            continue

        if marks is not None:
            try:
                marks = int(marks)
            except (ValueError, TypeError):
                marks = None

        if not isinstance(text, str) or not text.strip():
            continue

        # Restore LaTeX commands corrupted by JSON escape interpretation.
        # CR, TAB, BS, FF never belong in exam question text — they're always
        # corrupted \r \t \b \f from LaTeX commands like \rightarrow, \theta, etc.
        text = text.replace('\r', '\\r')
        text = text.replace('\t', '\\t')
        text = text.replace('\b', '\\b')
        text = text.replace('\f', '\\f')

        validated.append({
            "id": qid,
            "marks": marks,
            "text": text.strip(),
        })

    return validated


def _fix_latex_escapes(text: str) -> str:
    """Escape backslashes that aren't valid JSON escape sequences.

    LLM output contains LaTeX like \\( x^2 \\) inside JSON strings.
    JSON only allows \\\\ \\" \\/ \\b \\f \\n \\r \\t \\uXXXX — anything else
    causes json.loads to fail.
    """
    # First: escape \b \f \r \t that are part of LaTeX commands
    # (followed by lowercase alpha, meaning they're LaTeX like \rightarrow, \theta, etc.)
    text = re.sub(r'(?<!\\)\\([bfrt])(?=[a-z])', r'\\\\\1', text)
    # Then: escape remaining backslashes that aren't valid JSON escapes
    return re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', text)


def _repair_truncated_json(text: str) -> Optional[list]:
    """
    Retry continued from truncated response (i hate gemini for doing this so often)
    """
    # Find opening bracket
    start = text.find('[')
    if start == -1:
        return None

    # Find the last complete object boundary
    last_brace = text.rfind('}')
    if last_brace == -1 or last_brace <= start:
        return None

    # Take everything from `[` to the last `}` and close the array
    repaired = text[start:last_brace + 1] + ']'

    for fix_fn in [lambda s: s, _fix_latex_escapes]:
        try:
            result = json.loads(fix_fn(repaired))
            if isinstance(result, list) and len(result) > 0:
                logger.warning(
                    "Recovered %d questions from truncated JSON response",
                    len(result),
                )
                return result
        except json.JSONDecodeError:
            continue

    return None


def _merge_questions(accumulated: List[Dict], new: List[Dict]) -> List[Dict]:
    """Merge two question lists, deduplicating by ID (keeps first occurrence)."""
    seen_ids = {q["id"] for q in accumulated}
    merged = list(accumulated)
    for q in new:
        if q["id"] not in seen_ids:
            merged.append(q)
            seen_ids.add(q["id"])
    return merged


def _extract_json_array(text: str) -> Optional[list]:
    """Try to extract a JSON array from LLM output, with fallbacks."""
    text = text.strip()

    # Strip markdown fences (```json ... ``` or ``` ... ```)
    fence_match = re.match(r'^```(?:json)?\s*\n?(.*?)\n?\s*```$', text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    candidates = [text]
    bracket_match = re.search(r'\[.*\]', text, re.DOTALL)
    if bracket_match:
        candidates.append(bracket_match.group())

    for candidate in candidates:
        for fix_fn in [lambda s: s, _fix_latex_escapes]:
            try:
                result = json.loads(fix_fn(candidate))
                if isinstance(result, list):
                    return result
                # Handle wrapper objects like {"questions": [...]}
                if isinstance(result, dict):
                    for value in result.values():
                        if isinstance(value, list):
                            return value
            except json.JSONDecodeError:
                continue

    logger.warning("Failed to extract JSON array from response: %.500s", text)
    return None


def _safe_status(on_status: Optional[Callable[[str], None]], msg: str) -> None:
    """Call on_status without letting exceptions propagate."""
    if not on_status:
        return
    try:
        on_status(msg)
    except Exception:
        logger.warning("on_status callback failed", exc_info=True)


def parse_pdf_with_vision(pdf_path: str, max_retries: int = 2, on_status: Optional[Callable[[str], None]] = None) -> List[Dict]:
    """
    Send a PDF directly to Gemini Flash as a document and extract questions.
    Bypasses OCR entirely — Gemini reads the PDF visually.

    Returns a list of validated question dicts.
    Raises on failure.
    """
    from pathlib import Path

    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pdf_bytes = pdf_file.read_bytes()
    client = _get_client()

    accumulated_questions: List[Dict] = []
    continuation_context: Optional[str] = None
    last_error = None

    for attempt in range(max_retries + 1):
        if continuation_context:
            _safe_status(on_status, f"Gemini Vision: response truncated, requesting continuation (attempt {attempt + 1}/{max_retries + 1})...")
        else:
            _safe_status(on_status, f"Gemini Vision: parsing questions (attempt {attempt + 1}/{max_retries + 1})...")

        try:
            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=SYSTEM_PROMPT)],
                ),
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=FEW_SHOT_USER)],
                ),
                types.Content(
                    role="model",
                    parts=[types.Part.from_text(text=FEW_SHOT_RESPONSE)],
                ),
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(
                            data=pdf_bytes,
                            mime_type="application/pdf",
                        ),
                        types.Part.from_text(
                            text="Extract all questions from this exam paper."
                        ),
                    ],
                ),
            ]

            if continuation_context:
                contents.append(types.Content(
                    role="model",
                    parts=[types.Part.from_text(text=continuation_context)],
                ))
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=CONTINUE_PROMPT)],
                ))

            response = client.models.generate_content(
                model=MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=0,
                    max_output_tokens=65536,
                    thinking_config=ThinkingConfig(thinking_budget=0),
                    response_mime_type="application/json",
                    response_schema=_QUESTION_SCHEMA,
                ),
            )

            content = response.text
            parsed = _extract_json_array(content)

            if parsed is None:
                # Try truncation recovery
                recovered = _repair_truncated_json(content)
                if recovered:
                    validated_partial = validate_questions(recovered)
                    if validated_partial:
                        accumulated_questions = _merge_questions(accumulated_questions, validated_partial)
                        continuation_context = content
                        logger.warning(
                            "Gemini vision attempt %d truncated, recovered %d questions (%d total so far)",
                            attempt + 1, len(validated_partial), len(accumulated_questions),
                        )
                        raise ValueError(f"Truncated response, recovered {len(validated_partial)} questions")
                raise ValueError("Could not extract JSON array from Gemini vision response")

            validated = validate_questions(parsed)
            all_questions = _merge_questions(accumulated_questions, validated)
            if not all_questions:
                raise ValueError("No valid questions after validation")

            logger.info(
                "Gemini vision parser extracted %d questions from %s",
                len(all_questions), pdf_path,
            )
            return all_questions

        except Exception as e:
            last_error = e
            logger.warning(
                "Gemini vision attempt %d/%d failed: %s",
                attempt + 1, max_retries + 1, e,
            )

    raise RuntimeError(
        f"Gemini vision parsing failed after {max_retries + 1} attempts: {last_error}"
    )


def parse_with_llm(file_path: str, max_retries: int = 2, on_status: Optional[Callable[[str], None]] = None) -> List[Dict]:
    """
    Parse an exam markdown file using Gemini Flash API.

    Sends the full preprocessed paper in a single API call and gets back
    all questions as a JSON array.

    Raises on failure (caller should handle fallback).
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        raw_text = f.read()

    processed = preprocess_markdown(raw_text)
    if not processed.strip():
        raise ValueError("No question content found after preprocessing")

    client = _get_client()

    accumulated_questions: List[Dict] = []
    continuation_context: Optional[str] = None
    last_error = None

    for attempt in range(max_retries + 1):
        if continuation_context:
            _safe_status(on_status, f"LLM parser: response truncated, requesting continuation (attempt {attempt + 1}/{max_retries + 1})...")
        else:
            _safe_status(on_status, f"LLM parser: parsing questions (attempt {attempt + 1}/{max_retries + 1})...")

        try:
            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=SYSTEM_PROMPT)],
                ),
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=FEW_SHOT_USER)],
                ),
                types.Content(
                    role="model",
                    parts=[types.Part.from_text(text=FEW_SHOT_RESPONSE)],
                ),
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=processed)],
                ),
            ]

            if continuation_context:
                contents.append(types.Content(
                    role="model",
                    parts=[types.Part.from_text(text=continuation_context)],
                ))
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=CONTINUE_PROMPT)],
                ))

            response = client.models.generate_content(
                model=MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=0,
                    max_output_tokens=65536,
                    thinking_config=ThinkingConfig(thinking_budget=0),
                    response_mime_type="application/json",
                    response_schema=_QUESTION_SCHEMA,
                ),
            )

            content = response.text
            parsed = _extract_json_array(content)

            if parsed is None:
                # Try truncation recovery
                recovered = _repair_truncated_json(content)
                if recovered:
                    validated_partial = validate_questions(recovered)
                    if validated_partial:
                        accumulated_questions = _merge_questions(accumulated_questions, validated_partial)
                        continuation_context = content
                        logger.warning(
                            "LLM parser attempt %d truncated, recovered %d questions (%d total so far)",
                            attempt + 1, len(validated_partial), len(accumulated_questions),
                        )
                        raise ValueError(f"Truncated response, recovered {len(validated_partial)} questions")
                raise ValueError("Could not extract JSON array from Gemini response")

            validated = validate_questions(parsed)
            all_questions = _merge_questions(accumulated_questions, validated)
            if not all_questions:
                raise ValueError("No valid questions after validation")

            logger.info(
                "Gemini parser extracted %d questions from %s",
                len(all_questions), file_path,
            )
            return all_questions

        except Exception as e:
            last_error = e
            logger.warning(
                "Gemini parse attempt %d/%d failed: %s",
                attempt + 1, max_retries + 1, e,
            )

    raise RuntimeError(
        f"Gemini parsing failed after {max_retries + 1} attempts: {last_error}"
    )
