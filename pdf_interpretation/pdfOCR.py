import subprocess
import sys
import uuid
from pathlib import Path
import os

api_key = os.environ.get('CIRRASCALE_API_KEY')

def run_olmocr(
    pdf_path: str,
    api_key: str,
    output_dir: str = r"C:\Temp\pdf_test",
    model: str = "olmOCR-2-7B-1025",
) -> Path:
    """
    Run olmOCR on a single PDF and return the generated markdown file path.
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
        "--api_key", api_key,
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
    md_files = list(workspace.rglob("*.md"))
    if not md_files:
        raise RuntimeError(
            f"olmOCR completed but no markdown file was produced.\n{result.stdout}"
        )

    # Usually only one file
    return md_files[0]

md_path = run_olmocr(
    pdf_path="C:\Users\kdleg\OneDrive\Desktop\Topic Tracker\pdf_interpretation\Test_pdfs\ShortExam.pdf",
    api_key=api_key
)

print("Markdown generated at:", md_path)
print(md_path.read_text(encoding="utf-8"))