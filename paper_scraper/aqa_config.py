SPECS = {
    "7367": "A-level Further Mathematics",
    "7357": "A-level Physics",
    "7402": "A-level Biology",
    "7408": "A-level Chemistry",
    "7192": "A-level Sociology",
    "7182": "A-level Psychology",
    "7152": "A-level Politics",
    "7042": "A-level History",
    "7712": "A-level English Language",
}

OUTPUT_DIR = "paper_scraper/papers"
METADATA_FILE = "paper_scraper/index.json"
BASE_URL = "https://www.aqa.org.uk"
PAST_PAPERS_URL = "https://www.aqa.org.uk/find-past-papers-and-mark-schemes"

# Selector for items-per-page dropdown (verify at runtime)
ITEMS_PER_PAGE_SELECTOR = "select[aria-label*='Items per page'], select[name*='pageSize'], select[aria-label*='items per page']"

# Rate limiting
PAGE_DELAY_S = 1.5       # seconds between page navigations
DOWNLOAD_DELAY_S = 1.0   # seconds between PDF downloads

# Papers from years after MAX_YEAR are skipped (typically still locked/unreleased).
# Raise this once a series becomes publicly available.
MAX_YEAR = 2024
