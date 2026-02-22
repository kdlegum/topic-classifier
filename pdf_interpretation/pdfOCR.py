import subprocess
import sys
import uuid
from pathlib import Path
import os
import shutil
import json
import fitz
from pdf_interpretation.utils import updateStatus


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
) -> tuple[Path, str]:
    """
    Run olmOCR on a single PDF.
    Returns (markdown_path, workspace_path).
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
        timeout=60,
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
            # Log all files in workspace for debugging
            all_files = []
            for root, dirs, files in os.walk(workspace):
                for f in files:
                    all_files.append(os.path.join(root, f))
            raise FileNotFoundError(
                f"No matching md file found. Checked {expected_md_path} "
                f"and searched {workspace_md_dir}\n"
                f"STDOUT:\n{result.stdout}\n"
                f"STDERR:\n{result.stderr}\n"
                f"All workspace files:\n" + "\n".join(all_files)
            )
        expected_md_path = found

    os.makedirs(output_dir, exist_ok=True)

    new_path = os.path.join(output_dir, os.path.basename(expected_md_path))
    shutil.move(expected_md_path, new_path)
    print(f"Successfully migrated {expected_md_path} to {new_path}")

    # Keep the workspace — its results/ JSONL is used by the question locator backup
    return new_path, str(workspace)