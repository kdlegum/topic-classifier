import subprocess
import sys
import uuid
import re
from pathlib import Path
import os
import shutil
import json
import fitz
from pdf_interpretation.utils import updateStatus

# olmOCR renders pages with the longest dimension scaled to this many pixels
OLMOCR_TARGET_DIM = 2048


def extract_olmocr_images(pdf_path: str, jsonl_path: str, dest_dir: str) -> int:
    """
    Extract diagram images from a PDF by cropping regions that olmOCR referenced.

    olmOCR outputs image references like ![alt](page_X_Y_W_H.png) where
    X, Y, W, H are pixel coordinates in the rendered page image
    (max dimension = OLMOCR_TARGET_DIM pixels).

    Uses the JSONL text field and pdf_page_numbers attribute to determine
    which PDF page each image belongs to, renders that page with PyMuPDF,
    and crops.

    Returns the number of images extracted.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Read JSONL for the original text and pdf_page_numbers mapping
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        data = json.loads(f.readline())

    jsonl_text = data.get('text', '')
    page_ranges = data.get('attributes', {}).get('pdf_page_numbers', [])

    # Search in the JSONL text (character offsets match pdf_page_numbers)
    img_pattern = re.compile(r'!\[([^\]]*)\]\((page_(\d+)_(\d+)_(\d+)_(\d+)\.png)\)')
    img_refs = []
    for m in img_pattern.finditer(jsonl_text):
        filename = m.group(2)
        x, y, w, h = int(m.group(3)), int(m.group(4)), int(m.group(5)), int(m.group(6))
        char_pos = m.start()

        # Determine which page this image is on via character offset
        page_num = 1
        for start, end, pg in page_ranges:
            if start <= char_pos < end:
                page_num = pg
                break

        img_refs.append({
            'filename': filename,
            'x': x, 'y': y, 'w': w, 'h': h,
            'page': page_num,  # 1-indexed
        })

    if not img_refs:
        return 0

    doc = fitz.open(str(pdf_path))
    count = 0

    for ref in img_refs:
        page_idx = ref['page'] - 1  # 0-indexed
        if page_idx < 0 or page_idx >= len(doc):
            print(f"Skipping {ref['filename']}: page {ref['page']} out of range")
            continue

        page = doc[page_idx]
        rect = page.rect
        max_dim = max(rect.width, rect.height)
        zoom = OLMOCR_TARGET_DIM / max_dim

        # Convert pixel coordinates back to PDF points for clipping
        x, y, w, h = ref['x'], ref['y'], ref['w'], ref['h']
        clip = fitz.Rect(x / zoom, y / zoom, (x + w) / zoom, (y + h) / zoom)

        # Clamp to page bounds
        clip = clip & page.rect

        if clip.is_empty:
            print(f"Skipping {ref['filename']}: clip region empty after clamping")
            continue

        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, clip=clip)

        dest_file = dest_dir / ref['filename']
        pix.save(str(dest_file))
        count += 1

    doc.close()
    print(f"Extracted {count} diagram image(s) from {pdf_path} to {dest_dir}")
    return count


def extract_text_pymupdf(pdf_path: str, output_dir: str = "Backend/uploads/markdown") -> Path:
    """
    Extract text from a PDF using PyMuPDF's embedded text layer.
    Returns the path to the generated .md file.
    """
    pdf_path = Path(pdf_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(str(pdf_path))
    pages_text = []
    for page in doc:
        pages_text.append(page.get_text())
    doc.close()

    full_text = "\n\n".join(pages_text)

    if not full_text.strip():
        raise ValueError("PyMuPDF extracted no text from PDF (possibly a scanned document)")

    stem = pdf_path.stem
    out_path = output_dir / f"{stem}.md"
    out_path.write_text(full_text, encoding="utf-8")

    return out_path

def run_olmocr(
    pdf_path: str,
    output_dir: str = os.path.join(os.environ.get("TMPDIR", "/tmp"), "pdf_ocr_output"),
    model: str = "olmOCR-2-7B-1025",
) -> Path:
    """
    Run olmOCR on a single PDF and return the generated markdown file path.
    Also extracts diagram images by cropping PDF regions referenced in the markdown.
    """

    pdf_path = Path(pdf_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    # Isolate each run (VERY important for APIs)
    run_id = uuid.uuid4().hex
    workspace = output_dir / f"workspace_{run_id}"
    workspace.mkdir()

    env = dict(**dict(**subprocess.os.environ))
    env["PYTHONIOENCODING"] = "utf-8"
    env["TMP"] = str(output_dir)
    env["TEMP"] = str(output_dir)

    cmd = [
        sys.executable,
        "-m",
        "olmocr.pipeline",
        str(workspace),
        "--server", "https://ai2endpoints.cirrascale.ai/api",
        "--api_key", os.environ.get('CIRRASCALE_API_KEY'),
        "--model", model,
        "--workers", "1",
        "--pages_per_group", "2",
        "--markdown",
        "--skip_pdf_sampling",
        "--pdfs", str(pdf_path),
    ]

    result = subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"olmOCR failed:\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
        )

    # Find generated markdown
    input_file_name = os.path.splitext(os.path.basename(pdf_path))[0]
    expected_md_name = input_file_name + ".md"

    # olmocr places markdown inside workspace/markdown/ mirroring the full input path
    # Search both the original location (next to PDF) and inside the workspace
    expected_md_path = os.path.join(os.path.dirname(pdf_path), expected_md_name)

    if not os.path.exists(expected_md_path):
        # Search recursively inside workspace/markdown/
        workspace_md_dir = workspace / "markdown"
        found = None
        for root, dirs, files in os.walk(workspace_md_dir):
            if expected_md_name in files:
                found = os.path.join(root, expected_md_name)
                break
        if found is None:
            raise FileNotFoundError(
                f"No matching md file found. Checked {expected_md_path} "
                f"and searched {workspace_md_dir}"
            )
        expected_md_path = found

    os.makedirs(output_dir, exist_ok=True)

    new_path = os.path.join(output_dir, os.path.basename(expected_md_path))
    shutil.move(expected_md_path, new_path)
    print(f"Successfully migrated {expected_md_path} to {new_path}")

    # Extract diagram images using olmOCR's coordinate references
    # Find the JSONL results file in the workspace
    results_dir = workspace / "results"
    jsonl_files = list(results_dir.glob("*.jsonl")) if results_dir.exists() else []

    if jsonl_files:
        jsonl_path = str(jsonl_files[0])
        images_dest = Path("Backend/uploads/images") / input_file_name
        try:
            count = extract_olmocr_images(str(pdf_path), jsonl_path, str(images_dest))
            if count:
                print(f"Extracted {count} diagram image(s) for {input_file_name}")
        except Exception as e:
            print(f"Warning: diagram image extraction failed: {e}")
    else:
        print("Warning: no JSONL results found in workspace, skipping image extraction")

    # Cleanup workspace artifacts (everything except .md files in output_dir)
    for item in os.listdir(output_dir):
        item_path = os.path.join(output_dir, item)
        if os.path.isfile(item_path):
            if not item.lower().endswith(".md"):
                os.remove(item_path)
        else:
            shutil.rmtree(item_path)

    return new_path
