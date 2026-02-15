from google import genai
from google.genai import types
import json
import time
import itertools
import argparse

MODELS = ["gemini-3-pro-preview", "gemini-3-flash-preview"]


def build_prompt(qualification: str, subject: str, board: str, code: str) -> str:
    return f"""Extract the exam specification from this PDF into structured JSON matching this exact schema:

{{
  "Qualification": "{qualification}",
  "Subject": "{subject}",
  "Exam Board": "{board}",
  "Specification": "{code}",
  "has_math": <true if subject involves mathematical notation>,
  "optional_modules": <true if students choose module subsets>,
  "Topics": [
    {{
      "Topic_id": 1,
      "Specification_section": "<section heading from spec>",
      "Strand": "<overarching theme/module name>",
      "Topic_name": "<exact topic name from spec>",
      "Sub_topics": [
        {{
          "subtopic_id": "1a",
          "Specification_section_sub": "<spec reference e.g. 1.1a or Pp5>",
          "Sub_topic_name": "<exact subtopic name>",
          "description": "<ALL learning outcomes, notes, and notation text>"
        }}
      ]
    }}
  ]
}}

Rules:
1. Topic names must match the spec exactly. Combine (a)/(b) variants into one topic.
2. Strand = the overarching theme (e.g. Pure Mathematics, Organic Chemistry, Mechanics).
3. subtopic_id format: TopicNumber + letter (1a, 1b, 2a, 2b...).
4. Description must include ALL learning outcome text, notes, and notation columns.
5. Combine subtopics with multiple learning outcomes into one entry.
6. Skip asterisked/optional subtopics.
7. Output valid JSON only, no commentary.
8. Cover ALL strands, topics, and subtopics in the document.
9. If the JSON is too long for a single response, stop cleanly after a complete topic object.
"""


def try_parse_json(text):
    """Attempt strict JSON parse, then fallback repair attempts."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try trimming whitespace or trailing commas
    repaired = text.strip()
    repaired = repaired.replace("\n", "")

    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        return None


def generate_with_retry(pdf_bytes, client, prompt):
    """Retry indefinitely, alternating models until valid JSON is produced."""
    model_cycle = itertools.cycle(MODELS)
    attempt = 1

    while True:
        model = next(model_cycle)
        print(f"\n--- Attempt {attempt} using model: {model} ---")

        try:
            stream = client.models.generate_content_stream(
                model=model,
                contents=[
                    types.Part.from_bytes(
                        data=pdf_bytes,
                        mime_type="application/pdf",
                    ),
                    prompt,
                ],
                config={
                    "response_mime_type": "application/json",
                    "temperature": 0,
                    "max_output_tokens": 100000,
                },
            )

            full_text = ""
            for chunk in stream:
                if chunk.text:
                    print(chunk.text, end="", flush=True)
                    full_text += chunk.text

            print("\n\nAttempting to parse JSON...")

            parsed = try_parse_json(full_text)
            if parsed is not None:
                print("JSON parsed successfully.")
                return parsed

            print("JSON parsing failed. Retrying...")

        except Exception as e:
            print(f"Error during generation: {e}")

        attempt += 1
        time.sleep(2)  # small delay to avoid hammering API


def main():
    parser = argparse.ArgumentParser(description="Extract exam spec from PDF into structured JSON")
    parser.add_argument("--pdf", required=True, help="Path to the specification PDF")
    parser.add_argument("--qualification", required=True, help="e.g. 'A Level', 'GCSE'")
    parser.add_argument("--subject", required=True, help="e.g. 'Physics', 'Further Mathematics B (MEI)'")
    parser.add_argument("--board", required=True, help="e.g. 'OCR', 'Edexcel', 'AQA'")
    parser.add_argument("--code", required=True, help="Specification code e.g. 'H556'")
    parser.add_argument("--output", default=None, help="Output JSON path (default: <code>.json)")
    args = parser.parse_args()

    output_path = args.output or f"{args.code}.json"
    prompt = build_prompt(args.qualification, args.subject, args.board, args.code)

    client = genai.Client()

    with open(args.pdf, "rb") as f:
        pdf_bytes = f.read()

    print(f"Extracting {args.subject} ({args.code}) from {args.pdf}...")
    print("Starting extraction with automatic retries...\n")

    data = generate_with_retry(pdf_bytes, client, prompt)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\nDone. Saved to {output_path}")


if __name__ == "__main__":
    main()
