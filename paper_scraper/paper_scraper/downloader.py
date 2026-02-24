import os
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def make_session() -> requests.Session:
    """Return a requests.Session with automatic retry on transient failures."""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1.0,           # waits 1s, 2s, 4s between attempts
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://",  HTTPAdapter(max_retries=retry))
    return session


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
