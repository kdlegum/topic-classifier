import json
import os
from pathlib import Path

def updateStatus(job_id: str, newStatus: str):

    path = Path("Backend") / "uploads" / "status" / f"{job_id}.json"

    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found at path: {path}")
    
    with open(path, "r") as f:
        status = json.load(f)
    
    status["status"] = newStatus

    with open(path, "r") as f:
        json.dump(status, f)
    
    return True