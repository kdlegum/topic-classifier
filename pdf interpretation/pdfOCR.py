import fitz  # PyMuPDF
from eqInterpretation import toText
# Load PDF and get the first page
doc = fitz.open("exam.pdf")
page = doc[3]

# Get blocks
blocks = page.get_text("dict")["blocks"]

# Sort blocks by vertical position
blocks = sorted(blocks, key=lambda b: b["bbox"][1])

# Detect questions and subparts
questions = []
current_question = {"blocks": [], "top": None, "bottom": None}

for block in blocks:
    if block["type"] != 0:  # skip non-text blocks
        continue
    text = " ".join(span["text"] for line in block["lines"] for span in line["spans"]).strip()

    # crude detection of new question
    if text.startswith(tuple(str(i) for i in range(1, 20))) or text.startswith("(a)") or text.startswith("(b)"):
        if current_question["blocks"]:
            questions.append(current_question)
            current_question = {"blocks": [], "top": None, "bottom": None}
    
    # Update coordinates
    top = block["bbox"][1]
    bottom = block["bbox"][3]
    if current_question["top"] is None or top < current_question["top"]:
        current_question["top"] = top
    if current_question["bottom"] is None or bottom > current_question["bottom"]:
        current_question["bottom"] = bottom

    current_question["blocks"].append(block)

# Append last question
if current_question["blocks"]:
    questions.append(current_question)

# Print detected question coordinates
for i, q in enumerate(questions):
    print(f"Question {i+1}: top={q['top']:.1f}, bottom={q['bottom']:.1f}, blocks={len(q['blocks'])}")

    rect = fitz.Rect(0, q['top'], page.rect.width, q['bottom'])
    question_img = page.get_pixmap(clip=rect)
    question_img.save(f"question_{i+1}.png")

    print(toText(f"question_{i+1}.png"))



