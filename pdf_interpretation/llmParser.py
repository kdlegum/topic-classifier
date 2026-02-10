import re
import json
import logging
from typing import List, Dict, Optional

from google import genai
from google.genai import types

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
- Remove mark brackets like [3] from the text field.
- If a question has no sub-parts, output a single item with just the question number as id.
- Output ONLY the JSON array. No commentary, no markdown fences."""

FEW_SHOT_USER = """1 A shop sells two types of coffee.

(a) Type A costs £3.50 per bag. Calculate the cost of 4 bags. [2]

(b) Type B costs £4.20 per bag.

(i) Calculate the cost of 3 bags of Type B. [2]

(ii) Find the total cost of 4 bags of Type A and 3 bags of Type B. [3]

2 Solve the equation 3x + 5 = 20. [3]"""

FEW_SHOT_RESPONSE = """[
  {"id": "1a", "marks": 2, "text": "A shop sells two types of coffee. Type A costs £3.50 per bag. Calculate the cost of 4 bags."},
  {"id": "1b(i)", "marks": 2, "text": "A shop sells two types of coffee. Type B costs £4.20 per bag. Calculate the cost of 3 bags of Type B."},
  {"id": "1b(ii)", "marks": 3, "text": "A shop sells two types of coffee. Type A costs £3.50 per bag. Type B costs £4.20 per bag. Find the total cost of 4 bags of Type A and 3 bags of Type B."},
  {"id": "2", "marks": 3, "text": "Solve the equation 3x + 5 = 20."}
]"""

MODEL = "gemini-2.0-flash"


def preprocess_markdown(text: str) -> str:
    """Strip exam boilerplate and normalize the markdown for LLM parsing."""
    # Remove boilerplate before the first question.
    first_q = re.search(r'(?m)^\d+[\s.]', text)
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
    return re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', text)


def _extract_json_array(text: str) -> Optional[list]:
    """Try to extract a JSON array from LLM output, with fallbacks."""
    text = text.strip()

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
            except json.JSONDecodeError:
                continue

    return None


def parse_with_llm(file_path: str, max_retries: int = 2) -> List[Dict]:
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

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=[
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
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0,
                ),
            )

            content = response.text
            parsed = _extract_json_array(content)

            if parsed is None:
                raise ValueError("Could not extract JSON array from Gemini response")

            validated = validate_questions(parsed)
            if not validated:
                raise ValueError("No valid questions after validation")

            logger.info(
                "Gemini parser extracted %d questions from %s",
                len(validated), file_path,
            )
            return validated

        except Exception as e:
            last_error = e
            logger.warning(
                "Gemini parse attempt %d/%d failed: %s",
                attempt + 1, max_retries + 1, e,
            )

    raise RuntimeError(
        f"Gemini parsing failed after {max_retries + 1} attempts: {last_error}"
    )
