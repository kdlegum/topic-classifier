import json
import os
from pathlib import Path
from typing import Optional

def updateStatus(job_id: str, newStatus: str, session_id: Optional[str] = None, pipeline: Optional[str] = None):

    path = Path("Backend") / "uploads" / "status" / f"{job_id}.json"

    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found at path: {path}")

    with open(path, "r") as f:
        status = json.load(f)

    status["status"] = newStatus

    if session_id != None:
        status["session_id"] = session_id

    if pipeline is not None:
        status["pipeline"] = pipeline

    with open(path, "w") as f:
        json.dump(status, f)

    return True