# pdf_to_md.py
import os
from pdf2image import convert_from_path
from pix2text.pix_to_text import Pix2Text

# ==== CONFIG ====
pdf_path = "ShortExam.pdf"  # your PDF file
output_md = "exam.md"  # output Markdown file
poppler_path = r"C:\Poppler\poppler-23.01.0\Library\bin"  # path to Poppler bin
tmp_folder = "tmp_pages"  # folder to store temporary images

# ==== PREPARE ====
os.makedirs(tmp_folder, exist_ok=True)
model = Pix2Text()

# ==== CONVERT PDF TO IMAGES ====
print(f"Converting PDF to images: {pdf_path}")
pages = convert_from_path(pdf_path, poppler_path=poppler_path)

all_text = []

# ==== OCR EACH PAGE ====
for i, page in enumerate(pages, start=1):
    img_path = os.path.join(tmp_folder, f"page_{i}.png")
    page.save(img_path, "PNG")
    print(f"Processing page {i}/{len(pages)}...")

    text = model(img_path)  # call Pix2Text on image
    all_text.append(text)

# ==== SAVE OUTPUT ====

with open(output_md, "w", encoding="utf-8") as f:
    for i, page_blocks in enumerate(all_text, start=1):
        f.write(f"# Page {i}\n\n")
        # page_blocks is a list of dicts; get 'text' from each
        page_text = [block['text'] for block in page_blocks]
        f.write("\n".join(page_text))
        f.write("\n\n")

print(f"Done! Markdown saved to {output_md}")
