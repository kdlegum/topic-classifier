import re
from typing import List, Dict

TABLE_PATTERN = re.compile(
                        r"<table\b[^>]*>.*?</table>",
                        flags=re.IGNORECASE | re.DOTALL
                    )

def parse_exam_markdown_regex(file_path: str) -> List[Dict]:
    """
    Parse an exam Markdown file into structured questions using regex patterns.
    Returns a list of dicts:
      {
        "id": "2a(i)",
        "marks": 3,
        "text": "Full question text with diagrams and Unicode math"
      }
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()

    # --- Preprocess ---
    # Fix escaped LaTeX brackets \\( ... \\) -> \( ... \)
    text = text.replace(r'\\(', r'\(').replace(r'\\)', r'\)')
    # Replace images with [DIAGRAM]
    text = re.sub(r'!\[.*?\]\(.*?\)', '[DIAGRAM]', text)
    # Normalize whitespace
    text = re.sub(r'\n{3,}', '\n\n', text.strip())

    questions = []

    # --- Split main questions ---
    main_question_re = re.compile(
        r'(?m)^(?P<num>\d+)\s+(?P<body>.*?)(?=^\d+\s+|\Z)',
        re.DOTALL
    )

    for mq in main_question_re.finditer(text):
        q_num = mq.group('num')
        body = mq.group('body').strip()

        # --- Split top-level parts (a), (b), … ---
        top_part_re = re.compile(
            r'(?m)^\((?P<part>[a-z])\)\s+(?P<text>.*?)(?=^\([a-z]\)\s+|\Z)',
            re.DOTALL
        )
        top_parts = list(top_part_re.finditer(body))
        stem = body[:top_parts[0].start()].strip() if top_parts else ""

        if top_parts:
            for part in top_parts:
                part_id = f"{q_num}{part.group('part')}"
                part_text = part.group('text').strip()

                # --- Check for nested subparts (i), (ii), … ---
                nested_re = re.compile(
                    r'(?m)^\((?P<nested>[ivxlcdm]+)\)\s+(?P<text>.*?)(?=^\([ivxlcdm]+\)\s+|\Z)',
                    re.DOTALL
                )
                nested_matches = list(nested_re.finditer(part_text))

                if nested_matches:
                    for nm in nested_matches:
                        nested_id = f"{part_id}({nm.group('nested')})"
                        nested_text = nm.group('text').strip()

                        # Extract marks
                        marks_match = re.search(r'\[(\d+)\]', nested_text)
                        marks = int(marks_match.group(1)) if marks_match else None
                        nested_text = re.sub(r'\[\d+\]', '', nested_text).strip()

                        # Combine stem + nested part
                        full_text = f"{stem} {nested_text}" if stem else nested_text
                        # Filter the html tables
                        full_text = TABLE_PATTERN.sub("[TABLE]", full_text)
                        questions.append({
                            "id": nested_id,
                            "marks": marks,
                            "text": full_text
                        })
                else:
                    # No nested subparts
                    marks_match = re.search(r'\[(\d+)\]', part_text)
                    marks = int(marks_match.group(1)) if marks_match else None
                    part_text_clean = re.sub(r'\[\d+\]', '', part_text).strip()
                    full_text = f"{stem} {part_text_clean}" if stem else part_text_clean
                    full_text = TABLE_PATTERN.sub("[TABLE]", full_text)

                    questions.append({
                        "id": part_id,
                        "marks": marks,
                        "text": full_text
                    })
        else:
            # No subparts, whole body is one question
            marks_match = re.search(r'\[(\d+)\]', body)
            marks = int(marks_match.group(1)) if marks_match else None
            full_text = re.sub(r'\[\d+\]', '', body).strip()
            full_text = TABLE_PATTERN.sub("[TABLE]", full_text)
            questions.append({
                "id": q_num,
                "marks": marks,
                "text": full_text
            })

    return questions
