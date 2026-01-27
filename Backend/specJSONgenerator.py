from google import genai
from google.genai import types
import json
import time
import itertools

PDF_PATH = r"pdf_interpretation\Further_Maths_spec.pdf"
OUTPUT_JSON = "further_maths_spec.json"
RAW_OUTPUT = "further_maths_spec_raw.txt"

PROMPT = """You are an assistant that extracts the exam specification into structured JSON. Use the specification in the PDF provided. Output must match this JSON schema exactly: { "Qualification": "A Level", "Subject": "Further Mathematics B (MEI)", "Exam Board": "OCR", "Specification": "H645", "Topics": [ { "Topic_id": 1, "Specification_section": "Proof/Complex Numbers...", "Strand": "Core Pure/Mechanics Minor/Mechanics Major...", "Topic_name": "Exactly from spec", "Sub_topics": [ { "subtopic_id": "1a", "Specification_section_sub": "Exactly from spec, eg Pp5", "Sub_topic_name": "Exactly from spec", "description": "Exactly from spec, including learning outcomes, notes and notation." }, { "subtopic_id": "1b", ... } ] }, { "Topic_id": 2, ... } ] }
Instructions: 1. Name the topics exactly as they appear in the spec but you must ignore (a) (b), for example: Proof, Complex Numbers and so on. 2. The strand is the theme. For example, Pure Mathematics, Mechanics Minor, Statistics Major and so on. 3. For Specification_section_sub, use the reference used in the spec (Pp4, Pp5, Pj1). You must ignore subtopics that are labelled with an asterisk. For the subtopic_id, number using the format 1a, 1b, ... 2a, 2b... Where the number represents the topic and the letter represents the subtopic. 4. For the description, include all text from the learning outcomes, notes and notation column. 5. Some subtopics have more than 1 learning outome. You may combine these into one entry. 6. Do not invent descriptions or add extra topics. 7. Output must be valid JSON only. Do not add any commentary. 8. If the JSON is too long for a single response, stop cleanly after a complete topic object. 9. Output for all strands, topics and subtopics in the pdf file - the last topic is diophantine equations. 10. You must combine topics that have (a) and (b). Do not make them into separate topics.
"""

MODELS = ["gemini-3-pro-preview", "gemini-3-flash-preview"]


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


def generate_with_retry(pdf_bytes, client):
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
                    PROMPT,
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

            print("❌ JSON parsing failed. Retrying...")

        except Exception as e:
            print(f"❌ Error during generation: {e}")

        attempt += 1
        time.sleep(2)  # small delay to avoid hammering API


def main():
    client = genai.Client()

    with open(PDF_PATH, "rb") as f:
        pdf_bytes = f.read()

    print("Starting extraction with automatic retries...\n")

    data = generate_with_retry(pdf_bytes, client)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\nDone. Saved to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()