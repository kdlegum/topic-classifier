"""
Populate the paper cache by classifying past papers per spec.

Usage (run from project root, with the backend server running):
    python -m scripts.populate_cache [--base-url URL] [--spec-code CODE] [--count N]

Requires the FastAPI server to be running (default: https://localhost:8000).
For each spec with scraper support, it:
  1. Fetches the past papers list from the API
  2. Ranks QPs (preferring papers with a mark scheme, then most recent)
  3. Submits up to --count papers for classification via POST /classify-past-paper/{spec_code}
  4. Polls until each job completes, retrying with the next paper on failure

Already-cached papers are handled server-side (fast clone, no re-OCR).
"""

import argparse
import sys
import time
import uuid

import requests

DEFAULT_BASE_URL = "http://localhost:8000"
POLL_INTERVAL = 2  # seconds
POLL_TIMEOUT = 300  # 5 minutes max per paper


def get_specs(base_url: str) -> list[dict]:
    """Fetch all specs from the API."""
    resp = requests.get(f"{base_url}/specs")
    resp.raise_for_status()
    return resp.json()


def get_past_papers(base_url: str, spec_code: str, guest_id: str) -> list[dict]:
    """Fetch past papers for a spec (triggers auto-indexing on first call)."""
    resp = requests.get(
        f"{base_url}/past-papers",
        params={"spec_code": spec_code},
        headers={"X-Guest-ID": guest_id},
    )
    resp.raise_for_status()
    return resp.json()


def classify_paper(
    base_url: str, spec_code: str, content_id: str, guest_id: str, include_ms: bool
) -> str:
    """Submit a paper for classification, return the job_id."""
    resp = requests.post(
        f"{base_url}/classify-past-paper/{spec_code}",
        json={"content_id": content_id, "include_ms": include_ms},
        headers={"X-Guest-ID": guest_id},
    )
    resp.raise_for_status()
    return resp.json()["job_id"]


def poll_job(base_url: str, job_id: str) -> dict:
    """Poll until the job finishes. Returns the final status dict."""
    start = time.time()
    while time.time() - start < POLL_TIMEOUT:
        try:
            resp = requests.get(f"{base_url}/upload-pdf-status/{job_id}")
            resp.raise_for_status()
        except requests.HTTPError as e:
            return {"status": f"HTTP error: {e}"}
        except requests.ConnectionError as e:
            return {"status": f"Connection error: {e}"}
        data = resp.json()
        status = data.get("status", "")
        if status == "Done":
            return data
        if status == "failed" or status.startswith("Error"):
            return data
        time.sleep(POLL_INTERVAL)
    return {"status": "timeout"}


MAX_RETRIES = 3  # max papers to try per spec


def rank_papers(papers: list[dict]) -> list[dict]:
    """Rank papers for classification: prefer ones with a mark scheme, then most recent."""
    if not papers:
        return []
    # Prefer papers with a mark scheme
    with_ms = [p for p in papers if p.get("ms_content_id")]
    without_ms = [p for p in papers if not p.get("ms_content_id")]
    with_ms.sort(key=lambda p: (p.get("year") or 0), reverse=True)
    without_ms.sort(key=lambda p: (p.get("year") or 0), reverse=True)
    return with_ms + without_ms


def main():
    parser = argparse.ArgumentParser(description="Populate paper cache via the API")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Backend base URL")
    parser.add_argument("--spec-code", help="Only populate cache for this spec code")
    parser.add_argument("--include-ms", action="store_true", default=True,
                        help="Include mark scheme (default: true)")
    parser.add_argument("--no-ms", action="store_true", help="Skip mark scheme download")
    parser.add_argument("--count", type=int, default=1, help="Number of papers to cache per spec (default: 1)")
    parser.add_argument("--dry-run", action="store_true", help="List papers that would be classified without running")
    args = parser.parse_args()

    include_ms = not args.no_ms
    target_count = max(1, args.count)
    base_url = args.base_url.rstrip("/")
    guest_id = str(uuid.uuid4())

    print(f"Using guest ID: {guest_id}")
    print(f"Backend: {base_url}")
    print()

    # Get all specs
    try:
        specs = get_specs(base_url)
    except Exception as e:
        print(f"ERROR: Could not fetch specs from {base_url}/specs: {e}")
        print("Is the backend server running?")
        sys.exit(1)

    if args.spec_code:
        specs = [s for s in specs if s["spec_code"] == args.spec_code]
        if not specs:
            print(f"Spec code '{args.spec_code}' not found.")
            sys.exit(1)

    results = {"success": [], "failed": [], "skipped": []}

    for spec in specs:
        spec_code = spec["spec_code"]
        subject = spec.get("subject", "Unknown")
        print(f"--- {spec_code}: {subject} ---")

        # Fetch past papers (this triggers indexing if needed)
        try:
            papers = get_past_papers(base_url, spec_code, guest_id)
        except requests.HTTPError as e:
            print(f"  Could not fetch papers: {e}")
            results["skipped"].append((spec_code, "no papers endpoint"))
            continue
        except Exception as e:
            print(f"  Error fetching papers: {e}")
            results["skipped"].append((spec_code, str(e)))
            continue

        if not papers:
            print("  No past papers available")
            results["skipped"].append((spec_code, "no papers"))
            continue

        ranked = rank_papers(papers)
        if not ranked:
            print("  No suitable paper found")
            results["skipped"].append((spec_code, "no suitable paper"))
            continue

        if args.dry_run:
            for paper in ranked[:target_count]:
                year = paper.get("year", "?")
                series = paper.get("series", "?")
                paper_num = paper.get("paper_number", "?")
                has_ms = "yes" if paper.get("ms_content_id") else "no"
                print(f"  Would classify: {year} {series} Paper {paper_num} (MS: {has_ms})")
            results["success"].append((spec_code, f"dry-run ({min(len(ranked), target_count)} papers)"))
            continue

        cached_count = 0
        consecutive_failures = 0
        for paper in ranked:
            if cached_count >= target_count:
                break
            if consecutive_failures >= MAX_RETRIES:
                print(f"  Stopping after {MAX_RETRIES} consecutive failures")
                break

            year = paper.get("year", "?")
            series = paper.get("series", "?")
            paper_num = paper.get("paper_number", "?")
            has_ms = "yes" if paper.get("ms_content_id") else "no"
            print(f"  [{cached_count + 1}/{target_count}] {year} {series} Paper {paper_num} (MS: {has_ms})")

            # Submit for classification
            try:
                job_id = classify_paper(
                    base_url, spec_code, paper["content_id"], guest_id, include_ms and bool(paper.get("ms_content_id"))
                )
                print(f"    Job started: {job_id}")
            except requests.HTTPError as e:
                print(f"    Classification request failed: {e}")
                consecutive_failures += 1
                continue

            # Poll until done
            result = poll_job(base_url, job_id)
            status = result.get("status", "unknown")
            if status == "Done":
                session_id = result.get("session_id", "?")
                print(f"    Done! Session: {session_id}")
                cached_count += 1
                consecutive_failures = 0
            else:
                print(f"    Failed: {status}")
                consecutive_failures += 1

        if cached_count > 0:
            results["success"].append((spec_code, f"{cached_count}/{target_count} papers"))
        else:
            results["failed"].append((spec_code, "all attempts failed"))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Success: {len(results['success'])}")
    for code, sid in results["success"]:
        print(f"    {code}: {sid}")
    print(f"  Failed:  {len(results['failed'])}")
    for code, reason in results["failed"]:
        print(f"    {code}: {reason}")
    print(f"  Skipped: {len(results['skipped'])}")
    for code, reason in results["skipped"]:
        print(f"    {code}: {reason}")


if __name__ == "__main__":
    main()
