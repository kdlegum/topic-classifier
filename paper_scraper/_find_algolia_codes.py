"""Quick script to discover Algolia spec codes for new Edexcel specs."""
import re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import requests
from paper_scraper import edexcel_config as config

session = requests.Session()
headers = {
    "X-Algolia-Application-Id": config.ALGOLIA_APP_ID,
    "X-Algolia-API-Key": config.ALGOLIA_API_KEY,
    "Content-Type": "application/json",
}

# Specs to discover — edit this list as needed.
# Each entry is (spec_code, search_query).
# If search_query matches the spec_prefix, hits are filtered by filename prefix.
# For broader/keyword searches, set filter_by_prefix=False below.
SEARCHES = [
    ("9MA0", "9MA0"),
    ("9FM0", "9FM0"),
    # ── Additional A-level specs ──────────────────────────────────────────────
    ("9PL0", "9PL0"),  # Politics
    ("9RS0", "9RS0"),  # Religious Studies
    ("9PE0", "9PE0"),  # Physical Education
    ("9MU0", "9MU0"),  # Music
    ("9DR0", "9DR0"),  # Drama and Theatre
    ("9FA0", "9FA0"),  # Art and Design (Fine Art)
    ("9AD0", "9AD0"),  # Art and Design (Art, Craft and Design)
    ("9PY0", "9PY0"),  # Photography
    ("9DT0", "9DT0"),  # Design and Technology
    ("9LA0", "9LA0"),  # Law
    ("9FR0", "9FR0"),  # French
    ("9GN0", "9GN0"),  # German (spec_prefix 9GN0, not 9GE0)
    ("9SP0", "9SP0"),  # Spanish
    ("9IT0", "9IT0"),  # Italian
    ("9RU0", "9RU0"),  # Russian
    ("9CN0", "9CN0"),  # Chinese
    # ── Additional GCSE specs ─────────────────────────────────────────────────
    ("1DR0", "1DR0"),  # Drama
    ("1DA0", "1DA0"),  # Dance
    ("1MU0", "1MU0"),  # Music
    ("1FA0", "1FA0"),  # Fine Art
    ("1PY0", "1PY0"),  # Photography
    ("1PE0", "1PE0"),  # Physical Education
    ("1DT0", "1DT0"),  # Design and Technology
    ("1FR0", "1FR0"),  # French
    ("1GN0", "1GN0"),  # German
    ("1SP0", "1SP0"),  # Spanish
    ("1IT0", "1IT0"),  # Italian
    ("1RU0", "1RU0"),  # Russian
    ("1CN0", "1CN0"),  # Chinese
]

for spec_code, query in SEARCHES:
    payload = {"params": f"query={query}&hitsPerPage=10"}
    resp = session.post(config.ALGOLIA_ENDPOINT, headers=headers, json=payload, timeout=15)
    resp.raise_for_status()
    hits = resp.json().get("hits", [])

    found = set()
    for hit in hits:
        fname = (hit.get("url") or hit.get("id") or "").split("/")[-1].lower()
        if not fname.startswith(spec_code.lower()):
            continue
        for cat in hit.get("category", []):
            m = re.match(r"Pearson-UK:Specification-Code/(.+)", cat)
            if m:
                found.add(m.group(1))

    status = ", ".join(sorted(found)) if found else "NOT FOUND"
    print(f"{spec_code}: {status}")
