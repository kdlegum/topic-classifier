import json
from pathlib import Path

INPUT_FILE = Path("topics.json")
OUTPUT_FILE = Path("subtopics_index.json")


def build_subtopics_index(specs: list[dict]) -> dict:
    index = {}

    for spec in specs:
        qualification = spec.get("Qualification")
        subject = spec.get("Subject")
        exam_board = spec.get("Exam Board")
        specification = spec.get("Specification")

        for topic in spec.get("Topics", []):
            topic_id = topic.get("Topic_id")
            topic_name = topic.get("Topic_name")
            strand = topic.get("Strand")
            topic_spec_section = topic.get("Specification_section")

            for sub in topic.get("Sub_topics", []):
                spec_sub = sub.get("Specification_section_sub")

                # Make the key globally unique across specs
                key = f"{exam_board}_{specification}_{spec_sub}"

                if key in index:
                    raise ValueError(f"Duplicate sub-topic key detected: {key}")

                entry = {
                    "subtopic_id": sub.get("subtopic_id"),
                    "name": sub.get("Sub_topic_name"),
                    "description": sub.get("description"),

                    # Hierarchy metadata
                    "topic_id": topic_id,
                    "topic_name": topic_name,
                    "topic_specification_section": topic_spec_section,
                    "strand": strand,

                    # Global metadata
                    "qualification": qualification,
                    "subject": subject,
                    "exam_board": exam_board,
                    "specification": specification,
                    "spec_sub_section": spec_sub,

                    # Text used for embeddings / classification
                    "classification_text": (
                        f"{sub.get('Sub_topic_name')}. "
                        f"{sub.get('description')}"
                    )
                }

                index[key] = entry

    return index


def main():
    with INPUT_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # Allow both single-spec and multi-spec files gracefully
    if isinstance(data, dict):
        specs = [data]
    elif isinstance(data, list):
        specs = data
    else:
        raise TypeError("topics.json must be a dict or a list of dicts")

    flat_index = build_subtopics_index(specs)

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(flat_index, f, indent=2, ensure_ascii=False)

    print(f"Generated {len(flat_index)} sub-topics → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
