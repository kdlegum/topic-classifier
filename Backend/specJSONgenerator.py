from google import genai
from google.genai import types
import json

PDF_PATH = r"pdf_interpretation\Further_Maths_spec.pdf"
OUTPUT_JSON = "further_maths_spec.json"
PROMPT = """You are an assistant that extracts the exam specification into structured JSON. Use the specification in the PDF provided. Output must match this JSON schema exactly: { "Qualification": "A Level", "Subject": "Further Mathematics B (MEI)", "Exam Board": "OCR", "Specification": "H645", "Topics": [ { "Topic_id": 1, "Specification_section": "Proof/Complex Numbers...", "Strand": "Core Pure/Mechanics Minor/Mechanics Major...", "Topic_name": "Exactly from spec", "Sub_topics": [ { "subtopic_id": "1a", "Specification_section_sub": "Exactly from spec, eg Pp5", "Sub_topic_name": "Exactly from spec", "description": "Exactly from spec, including learning outcomes, notes and notation." }, { "subtopic_id": "1b", ... } ] }, { "Topic_id": 2, ... } ] } 
Instructions: 1. Name the topics exactly as they appear in the spec but you must ignore (a) (b), for example: Proof, Complex Numbers. 2. The strand is the theme. For example, Pure Mathematics, Mechanics Minor, Statistics Major. 3. For Specification_section_sub, use the reference used in the spec (Pp4, Pp5, Pj1). You must ignore subtopics that are labelled with an asterisk. For the subtopic_id, number using the format 1a, 1b, ... 2a, 2b... Where the number represents the topic and the letter represents the subtopic. 4. For the description, include all text from the learning outcomes, notes and notation column. 6. Do not invent descriptions or add extra topics. 7. Output must be valid JSON only. Do not add any commentary. 8. If the JSON is too long for a single response, stop cleanly after a complete topic object. 9. Output for all topics and subtopics in the pdf file. 10. You must combine topics that have (a) and (b). Do not make them into separate topics. """


# -----------------------------
# MAIN
# -----------------------------
def main():
    client = genai.Client()

    # Read PDF as bytes
    with open(PDF_PATH, "rb") as f:
        pdf_bytes = f.read()

    # Call Gemini with PDF + prompt
    response = client.models.generate_content(
        model="gemini-3-pro-preview",
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

    # Parse and save JSON
    data = json.loads(response.text)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Done. Saved to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()