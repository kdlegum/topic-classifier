import os
import time
import requests


def download_pdf(url: str, dest_path: str, session: requests.Session, delay_s: float = 1.0) -> bool:
    """Download a PDF to dest_path if not already present.

    Returns True if the file was downloaded, False if it already existed.
    Raises requests.HTTPError on non-2xx responses.
    """
    if os.path.exists(dest_path):
        return False

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    resp = session.get(
        url,
        timeout=30,
        headers={"User-Agent": "TopicTracker/1.0 Educational"},
    )
    resp.raise_for_status()

    with open(dest_path, "wb") as f:
        f.write(resp.content)

    time.sleep(delay_s)
    return True
