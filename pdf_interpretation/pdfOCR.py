import subprocess
import sys
import uuid
from pathlib import Path
import os
import shutil
import json
from pdf_interpretation.utils import updateStatus

def run_olmocr(
    pdf_path: str,
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

    # Find generated markdown which is made in same folder as pdf and move into the output directory
    input_directory_name = os.path.dirname(pdf_path)
    input_file_name = os.path.splitext(os.path.basename(pdf_path))[0]

    expected_md_path = os.path.join(input_directory_name, input_file_name + ".md")

    if not os.path.exists(expected_md_path):
        raise FileNotFoundError(f"No matching md file found with path {expected_md_path}.")

    os.makedirs(output_dir, exist_ok=True)

    new_path = os.path.join(output_dir, os.path.basename(expected_md_path))
    shutil.move(expected_md_path, new_path)
    print(f"Successfully migrated {expected_md_path} to {new_path}")

    #This is a temporary fix for the issue of a whole workspace folder moving no matter what i try
    for item in os.listdir(output_dir):
        item_path = os.path.join(output_dir, item)     
        if os.path.isfile(item_path):
            if not item.lower().endswith(".md"):
                os.remove(item_path)
                print(f"Deleted file: {item_path}")
        else:
            shutil.rmtree(item_path)
            print(f"Deleted folder: {item_path}")

    updateStatus(input_file_name, "Markdown Created. Extracting Questions...")

    return new_path