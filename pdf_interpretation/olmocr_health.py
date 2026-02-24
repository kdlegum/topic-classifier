"""
olmOCR health-check scheduler.

Runs a dummy PDF through olmOCR once on startup and then every hour.
If the check times out or raises, olmOCR is marked unhealthy and all
upload jobs bypass it (going straight to Gemini Vision) until the next
successful check.
"""

import logging
import os
import shutil
import tempfile
import threading
import time

logger = logging.getLogger(__name__)

_CHECK_INTERVAL: float = 3600.0  # seconds between periodic checks

_lock = threading.Lock()
_olmocr_healthy: bool = True   # optimistic default until first check completes
_last_check_time: float = 0.0
_last_result: str = "pending"  # "pending" | "pass" | "fail"


def is_olmocr_healthy() -> bool:
    """Return True if the most recent health check passed (or none has run yet)."""
    with _lock:
        return _olmocr_healthy


def get_status() -> dict:
    """Return a snapshot of the current health state for debug endpoints."""
    with _lock:
        return {
            "healthy": _olmocr_healthy,
            "last_result": _last_result,
            "last_check_time": _last_check_time or None,
            "next_check_in_seconds": (
                max(0.0, _CHECK_INTERVAL - (time.time() - _last_check_time))
                if _last_check_time else None
            ),
        }


def _set_state(healthy: bool, result: str) -> None:
    global _olmocr_healthy, _last_check_time, _last_result
    with _lock:
        _olmocr_healthy = healthy
        _last_check_time = time.time()
        _last_result = result


def _create_dummy_pdf(directory: str) -> str:
    """Create a minimal single-page PDF inside `directory` and return its path."""
    import fitz  # PyMuPDF — already a project dependency

    path = os.path.join(directory, "health_check.pdf")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "olmOCR health check. 1 + 1 = 2.")
    doc.save(path)
    doc.close()
    return path


def run_health_check() -> bool:
    """
    Run olmOCR on a tiny dummy PDF.
    Updates module-level health state and returns True on success.
    Safe to call from any thread.
    """
    logger.info("olmOCR health check starting…")
    out_dir: str | None = None

    try:
        from pdf_interpretation.pdfOCR import run_olmocr  # local import to avoid circular issues

        # Create out_dir first so the PDF lives inside it — olmOCR may try to
        # delete its input file, and that only works if we own the directory.
        out_dir = tempfile.mkdtemp(prefix="olmocr_health_")
        dummy_pdf = _create_dummy_pdf(out_dir)

        run_olmocr(dummy_pdf, output_dir=out_dir)

        _set_state(True, "pass")
        logger.info("olmOCR health check PASSED")
        return True

    except Exception as exc:
        _set_state(False, "fail")
        logger.warning("olmOCR health check FAILED: %s", exc)
        return False

    finally:
        if out_dir and os.path.exists(out_dir):
            shutil.rmtree(out_dir, ignore_errors=True)


def _scheduler_loop() -> None:
    """Background loop: sleep for CHECK_INTERVAL, then re-run the check."""
    while True:
        time.sleep(_CHECK_INTERVAL)
        try:
            run_health_check()
        except Exception:
            logger.exception("Unexpected error in olmOCR health scheduler")


def start_health_scheduler() -> None:
    """
    Kick off the health-check system.  Call once at application startup.

    - Runs an immediate check in a daemon thread so the app starts quickly.
    - Then a second daemon thread loops every hour running subsequent checks.
    """
    t_initial = threading.Thread(
        target=run_health_check,
        daemon=True,
        name="olmocr-health-initial",
    )
    t_initial.start()

    t_loop = threading.Thread(
        target=_scheduler_loop,
        daemon=True,
        name="olmocr-health-scheduler",
    )
    t_loop.start()

    logger.info(
        "olmOCR health-check scheduler started (interval=%ds)", int(_CHECK_INTERVAL)
    )
