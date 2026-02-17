# Usage (single spec):
#   python specJSONgenerator.py --pdf spec.pdf --qualification "A Level" --subject "Physics" --board "OCR" --code "H556"
#   python specJSONgenerator.py --pdf spec.pdf --qualification "GCSE" --subject "Mathematics" --board "Edexcel" --code "1MA1" --output out.json
#
# Usage (batch):
#   python specJSONgenerator.py --batch specs.json
#
#   specs.json format:
#   [
#     {"pdf": "path/to/spec.pdf", "qualification": "A Level", "subject": "Physics", "board": "OCR", "code": "H556"},
#     {"pdf": "path/to/spec2.pdf", "qualification": "GCSE", "subject": "Maths", "board": "AQA", "code": "8300", "output": "custom.json"}
#   ]
#
# Requires OPENAI_API_KEY environment variable.

import json
import base64
import time
import os
import argparse
from openai import OpenAI

MODEL = "gpt-5.2"


def build_prompt(qualification: str, subject: str, board: str, code: str) -> str:
    return f"""You are extracting a UK exam board specification PDF into structured JSON for a revision-tracking app.

## Context

The app uses this JSON to classify exam questions by topic. Each subtopic's description is
encoded into a vector embedding (using sentence-transformers) and compared against exam questions
via cosine similarity. This means:
- Descriptions must be semantically rich — include all learning outcomes, key terminology, and
  specific notation so the embedding captures the full meaning of the subtopic.
- Sub_topic_name should be a concise, recognisable label a student would understand.
- Every assessable point in the spec should appear as a subtopic somewhere — missing subtopics
  mean questions on that content can never be correctly classified.
- Subtopics must be as granular as possible. Each subtopic should correspond to a single testable
  concept or fact. If a spec bullet point covers multiple distinct ideas that could each appear
  as separate exam questions, split them into separate subtopics. Never lump together content
  that a student would revise independently — one subtopic = one thing to know or be able to do.

## Metadata for this specification

- Qualification: {qualification}
- Subject: {subject}
- Exam Board: {board}
- Specification Code: {code}

## Structural rules

1. **Topics** correspond to the major numbered sections in the spec (e.g. "1. Proof", "2. Algebra and functions").
   - Topic_id is a sequential integer starting at 1.
   - Specification_section is the section number/label from the spec (e.g. "1.1", "Topic 1").
   - Topic_name must match the spec wording exactly.
   - You may take some liberty where the spec does not provide a specific analogous section.

2. **Strands** group topics into overarching themes/modules (e.g. "Pure Mathematics", "Statistics",
   "Mechanics", "Organic Chemistry"). A spec with only one theme should use a single strand
   (e.g. "Physics"). If the spec has optional module pathways, set optional_modules to true.

3. **Subtopics** are the individual assessable points within a topic.
   - subtopic_id format: TopicNumber + lowercase letter, e.g. "1a", "1b", "2a", "2b".
     Letters restart at "a" for each new topic.
   - Specification_section_sub is the spec's own reference code (e.g. "1.1a", "Pp5", "3.2.1").
     Do NOT append tier labels here — keep it as the pure reference code.
   - Description must capture ALL learning outcome text, any notes/guidance columns, and
     mathematical notation. Concatenate multiple bullet points into one string if they belong
     to the same subtopic.
   - tier: set to a string (e.g. "Higher", "Supplement", "Extension") if the subtopic is
     restricted to a specific exam tier/level. Set to null if it is common to all tiers.

4. **Skip** explicitly optional content.

5. **Skip non-assessable administrative content.** Do NOT create subtopics for:
   - Course structure descriptions (e.g. "students study one period study and one thematic study")
   - Paper/component option listings (e.g. "Paper 1 Section A options: AA, AB, AC...")
   - Assessment rules (e.g. "British history must form 40% of assessed content")
   - Teaching time or weighting information (e.g. "indicative teaching time ~36 hours")
   - Study purpose/rationale statements (e.g. "develop ability to analyse interpretations")
   - Skills or assessment objective descriptions
   Only include content that a student could actually be **examined on** — i.e. substantive
   knowledge, understanding, or skills that appear as learning outcomes in the spec.

6. Set has_math to true if the subject involves mathematical notation (formulae, symbols, equations).

## Example output (OCR A Level Maths, first two topics)

```json
{{
  "Qualification": "A Level",
  "Subject": "Mathematics",
  "Exam Board": "OCR",
  "Specification": "H240",
  "has_math": true,
  "optional_modules": false,
  "Topics": [
    {{
      "Topic_id": 1,
      "Specification_section": "1.1",
      "Strand": "Pure Mathematics",
      "Topic_name": "Proof",
      "Sub_topics": [
        {{
          "subtopic_id": "1a",
          "Specification_section_sub": "1.1a",
          "Sub_topic_name": "Proof structure",
          "description": "Understand and be able to use the structure of mathematical proof, proceeding from given assumptions through a series of logical steps to a conclusion.",
          "tier": null
        }},
        {{
          "subtopic_id": "1b",
          "Specification_section_sub": "1.1b",
          "Sub_topic_name": "Logical connectives",
          "description": "Understand and be able to use the logical connectives (∧, ∨, ¬)",
          "tier": null
        }}
      ]
    }},
    {{
      "Topic_id": 2,
      "Specification_section": "1.2",
      "Strand": "Pure Mathematics",
      "Topic_name": "Algebra and functions",
      "Sub_topics": [
        {{
          "subtopic_id": "2a",
          "Specification_section_sub": "1.2a",
          "Sub_topic_name": "Laws of indices",
          "description": "Understand and be able to use the laws of indices for all rational exponents.",
          "tier": null
        }}
      ]
    }}
  ]
}}
```

Now extract the COMPLETE specification from the attached PDF. Cover every strand, topic, and subtopic."""


RESPONSE_SCHEMA = {
    "type": "json_schema",
    "name": "exam_specification",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "Qualification": {"type": "string"},
            "Subject": {"type": "string"},
            "Exam Board": {"type": "string"},
            "Specification": {"type": "string"},
            "has_math": {"type": "boolean"},
            "optional_modules": {"type": "boolean"},
            "Topics": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "Topic_id": {"type": "integer"},
                        "Specification_section": {"type": "string"},
                        "Strand": {"type": "string"},
                        "Topic_name": {"type": "string"},
                        "Sub_topics": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "subtopic_id": {"type": "string"},
                                    "Specification_section_sub": {"type": "string"},
                                    "Sub_topic_name": {"type": "string"},
                                    "description": {"type": "string"},
                                    "tier": {"type": ["string", "null"]},
                                },
                                "required": [
                                    "subtopic_id",
                                    "Specification_section_sub",
                                    "Sub_topic_name",
                                    "description",
                                    "tier",
                                ],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": [
                        "Topic_id",
                        "Specification_section",
                        "Strand",
                        "Topic_name",
                        "Sub_topics",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": [
            "Qualification",
            "Subject",
            "Exam Board",
            "Specification",
            "has_math",
            "optional_modules",
            "Topics",
        ],
        "additionalProperties": False,
    },
}


def extract_spec(pdf_path: str, prompt: str) -> dict:
    client = OpenAI()

    with open(pdf_path, "rb") as f:
        pdf_b64 = base64.b64encode(f.read()).decode("utf-8")

    print("Sending PDF to OpenAI...\n")

    stream = client.responses.create(
        model=MODEL,
        stream=True,
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_file",
                        "filename": "specification.pdf",
                        "file_data": f"data:application/pdf;base64,{pdf_b64}",
                    },
                    {"type": "input_text", "text": prompt},
                ],
            }
        ],
        text={"format": RESPONSE_SCHEMA},
    )

    full_text = ""
    for event in stream:
        if event.type == "response.output_text.delta":
            print(event.delta, end="", flush=True)
            full_text += event.delta

    print()  # newline after stream ends
    return json.loads(full_text)


BATCH_WAIT = 65  # seconds between batch items to avoid rate limits


def default_output_name(subject, board, code):
    safe_subject = subject.replace(" ", "_").replace("/", "-")
    return f"{safe_subject}_{board}_{code}.json"


def process_one(pdf, qualification, subject, board, code, output):
    """Extract a single spec and save to file. Returns (code, topic_count, subtopic_count)."""
    output_path = output or default_output_name(subject, board, code)
    prompt = build_prompt(qualification, subject, board, code)

    print(f"Extracting {subject} ({code}) from {pdf}...")

    data = extract_spec(pdf, prompt)

    topic_count = len(data.get("Topics", []))
    subtopic_count = sum(len(t.get("Sub_topics", [])) for t in data.get("Topics", []))
    print(f"Extracted {topic_count} topics, {subtopic_count} subtopics.")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Saved to {output_path}")
    return code, topic_count, subtopic_count


def main():
    parser = argparse.ArgumentParser(
        description="Extract exam spec from PDF into structured JSON"
    )
    parser.add_argument("--pdf", help="Path to the specification PDF")
    parser.add_argument("--qualification", help="e.g. 'A Level', 'GCSE'")
    parser.add_argument(
        "--subject",
        help="e.g. 'Physics', 'Further Mathematics B (MEI)'",
    )
    parser.add_argument("--board", help="e.g. 'OCR', 'Edexcel', 'AQA'")
    parser.add_argument("--code", help="Specification code e.g. 'H556'")
    parser.add_argument(
        "--output", default=None, help="Output JSON path (default: <code>.json)"
    )
    parser.add_argument(
        "--batch",
        default=None,
        help="Path to a JSON file with an array of specs to process",
    )
    args = parser.parse_args()

    if args.batch:
        with open(args.batch, encoding="utf-8") as f:
            specs = json.load(f)

        # Skip specs that already have output files
        remaining = []
        skipped = []
        for spec in specs:
            out = spec.get("output") or default_output_name(spec["subject"], spec["board"], spec["code"])
            if os.path.exists(out):
                skipped.append(spec["code"])
            else:
                remaining.append(spec)

        if skipped:
            print(f"Skipping {len(skipped)} already-completed specs: {', '.join(skipped)}")

        print(f"Batch mode: {len(remaining)} specs to process ({len(skipped)} skipped)\n")
        results = []
        failed = []

        def print_summary():
            print(f"\n{'='*60}")
            print(f"Batch summary: {len(results)} succeeded, {len(failed)} failed")
            for code, topics, subtopics in results:
                print(f"  {code}: {topics} topics, {subtopics} subtopics")
            if failed:
                print(f"\nFailed ({len(failed)}):")
                for code, err in failed:
                    print(f"  {code}: {err}")
            print(f"{'='*60}")

        try:
            for i, spec in enumerate(remaining):
                if i > 0:
                    print(f"\n--- Waiting {BATCH_WAIT}s before next spec ---\n")
                    time.sleep(BATCH_WAIT)

                print(f"\n{'='*60}")
                print(f"  [{i + 1}/{len(remaining)}] {spec['subject']} ({spec['code']})")
                print(f"{'='*60}\n")

                try:
                    result = process_one(
                        pdf=spec["pdf"],
                        qualification=spec["qualification"],
                        subject=spec["subject"],
                        board=spec["board"],
                        code=spec["code"],
                        output=spec.get("output"),
                    )
                    results.append(result)
                except Exception as e:
                    print(f"\nERROR processing {spec['code']}: {e}")
                    failed.append((spec["code"], str(e)))

        except KeyboardInterrupt:
            print("\n\nInterrupted! Printing progress so far...")

        print_summary()

    else:
        if not all([args.pdf, args.qualification, args.subject, args.board, args.code]):
            parser.error(
                "Single mode requires --pdf, --qualification, --subject, --board, --code"
            )
        process_one(args.pdf, args.qualification, args.subject, args.board, args.code, args.output)


if __name__ == "__main__":
    main()
