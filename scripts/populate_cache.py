"""
Populate the paper cache by classifying past papers per spec.

Usage (run from project root, with the backend server running):
    python -m scripts.populate_cache [--base-url URL] [--spec-code CODE] [--count N]

Requires the FastAPI server to be running (default: http://localhost:8000).
For each spec with scraper support, it:
  1. Fetches the past papers list from the API
  2. Ranks QPs (preferring papers with a mark scheme, then most recent)
  3. Submits up to --count papers for classification (concurrently across specs)
  4. Polls all running jobs in parallel until they complete

Already-cached papers are handled server-side (fast clone, no re-OCR).
"""

import argparse
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

DEFAULT_BASE_URL = "http://localhost:8000"
POLL_INTERVAL = 2  # seconds
POLL_TIMEOUT = 300  # 5 minutes max per paper
MAX_WORKERS = 4  # concurrent classification jobs


def get_specs(base_url: str) -> list[dict]:
    """Fetch all specs from the API."""
    resp = requests.get(f"{base_url}/specs")
    resp.raise_for_status()
    return resp.json()


def get_cache_stats(base_url: str) -> dict[str, int]:
    """Fetch cached paper counts per spec_code."""
    resp = requests.get(f"{base_url}/cache-stats")
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


def rank_papers(papers: list[dict]) -> list[dict]:
    """Rank papers for classification: prefer ones with a mark scheme, then most recent."""
    if not papers:
        return []
    with_ms = [p for p in papers if p.get("ms_content_id")]
    without_ms = [p for p in papers if not p.get("ms_content_id")]
    with_ms.sort(key=lambda p: (p.get("year") or 0), reverse=True)
    without_ms.sort(key=lambda p: (p.get("year") or 0), reverse=True)
    return with_ms + without_ms


def process_spec(
    base_url: str, spec: dict, guest_id: str, target_count: int,
    include_ms: bool, dry_run: bool
) -> tuple[str, str, str]:
    """Process a single spec: submit papers and poll for results.
    Returns (spec_code, status_category, detail)."""
    spec_code = spec["spec_code"]
    subject = spec.get("subject", "Unknown")
    label = f"{spec_code}: {subject}"

    try:
        papers = get_past_papers(base_url, spec_code, guest_id)
    except requests.HTTPError as e:
        return (spec_code, "skipped", f"could not fetch papers: {e}")
    except Exception as e:
        return (spec_code, "skipped", str(e))

    if not papers:
        return (spec_code, "skipped", "no past papers available")

    ranked = rank_papers(papers)
    if not ranked:
        return (spec_code, "skipped", "no suitable paper")

    if dry_run:
        lines = []
        for paper in ranked[:target_count]:
            year = paper.get("year", "?")
            series = paper.get("series", "?")
            paper_num = paper.get("paper_number", "?")
            has_ms = "yes" if paper.get("ms_content_id") else "no"
            lines.append(f"  Would classify: {year} {series} Paper {paper_num} (MS: {has_ms})")
        print(f"--- {label} ---")
        print("\n".join(lines))
        return (spec_code, "success", f"dry-run ({min(len(ranked), target_count)} papers)")

    print(f"--- {label} ---")
    cached_count = 0
    for paper in ranked:
        if cached_count >= target_count:
            break

        year = paper.get("year", "?")
        series = paper.get("series", "?")
        paper_num = paper.get("paper_number", "?")
        has_ms = "yes" if paper.get("ms_content_id") else "no"
        print(f"  [{cached_count + 1}/{target_count}] {year} {series} Paper {paper_num} (MS: {has_ms})")

        try:
            job_id = classify_paper(
                base_url, spec_code, paper["content_id"], guest_id,
                include_ms and bool(paper.get("ms_content_id"))
            )
            print(f"    Job started: {job_id}")
        except requests.HTTPError as e:
            print(f"    Classification request failed: {e}")
            continue

        result = poll_job(base_url, job_id)
        status = result.get("status", "unknown")
        if status == "Done":
            session_id = result.get("session_id", "?")
            print(f"    Done! Session: {session_id}")
            cached_count += 1
        else:
            print(f"    Failed: {status}")

    if cached_count > 0:
        return (spec_code, "success", f"{cached_count}/{target_count} papers")
    else:
        return (spec_code, "failed", "all attempts failed")


def main():
    parser = argparse.ArgumentParser(description="Populate paper cache via the API")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Backend base URL")
    parser.add_argument("--spec-code", help="Only populate cache for this spec code")
    parser.add_argument("--include-ms", action="store_true", default=True,
                        help="Include mark scheme (default: true)")
    parser.add_argument("--no-ms", action="store_true", help="Skip mark scheme download")
    parser.add_argument("--count", type=int, default=1, help="Number of papers to cache per spec (default: 1)")
    parser.add_argument("--dry-run", action="store_true", help="List papers that would be classified without running")
    parser.add_argument("--skip-cached", action="store_true",
                        help="Skip specs that already have >= --count cached papers")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS,
                        help=f"Max concurrent classification jobs (default: {MAX_WORKERS})")
    args = parser.parse_args()

    include_ms = not args.no_ms
    target_count = max(1, args.count)
    base_url = args.base_url.rstrip("/")
    guest_id = str(uuid.uuid4())

    print(f"Using guest ID: {guest_id}")
    print(f"Backend: {base_url}")
    print(f"Concurrency: {args.workers} workers")
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

    # Skip specs that already have enough cached papers
    cache_stats: dict[str, int] = {}
    if args.skip_cached:
        try:
            cache_stats = get_cache_stats(base_url)
        except Exception as e:
            print(f"WARNING: Could not fetch cache stats: {e}")
            print("Proceeding without skip-cached filtering.\n")

    specs_to_process = []
    results = {"success": [], "failed": [], "skipped": []}

    for spec in specs:
        spec_code = spec["spec_code"]
        if args.skip_cached and cache_stats.get(spec_code, 0) >= target_count:
            cached = cache_stats[spec_code]
            print(f"--- {spec_code}: {spec.get('subject', 'Unknown')} --- SKIPPED ({cached} already cached)")
            results["skipped"].append((spec_code, f"already cached ({cached} papers)"))
        else:
            specs_to_process.append(spec)

    if not specs_to_process:
        print("\nAll specs already have enough cached papers.")
    elif args.workers <= 1:
        # Sequential mode
        for spec in specs_to_process:
            code, category, detail = process_spec(
                base_url, spec, guest_id, target_count, include_ms, args.dry_run
            )
            results[category].append((code, detail))
    else:
        # Concurrent mode
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(
                    process_spec, base_url, spec, guest_id,
                    target_count, include_ms, args.dry_run
                ): spec
                for spec in specs_to_process
            }
            for future in as_completed(futures):
                try:
                    code, category, detail = future.result()
                    results[category].append((code, detail))
                except Exception as e:
                    spec = futures[future]
                    print(f"--- {spec['spec_code']} --- EXCEPTION: {e}")
                    results["failed"].append((spec["spec_code"], str(e)))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Success: {len(results['success'])}")
    for code, detail in results["success"]:
        print(f"    {code}: {detail}")
    print(f"  Failed:  {len(results['failed'])}")
    for code, reason in results["failed"]:
        print(f"    {code}: {reason}")
    print(f"  Skipped: {len(results['skipped'])}")
    for code, reason in results["skipped"]:
        print(f"    {code}: {reason}")


if __name__ == "__main__":
    main()
