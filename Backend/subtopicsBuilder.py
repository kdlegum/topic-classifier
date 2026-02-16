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
                key = f"{exam_board}_{specification}_{sub.get('subtopic_id')}"

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


