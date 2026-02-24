SPECS = {
    # — A-Level (AS & A2) —
    "7127": "A-level Accounting",
    "7201": "A-level Art and Design (Art, craft and design)",
    "7202": "A-level Art and Design (Fine art)",
    "7203": "A-level Art and Design (Graphic communication)",
    "7204": "A-level Art and Design (Textile design)",
    "7205": "A-level Art and Design (Three-dimensional design)",
    "7637": "A-level Bengali",
    "7402": "A-level Biology",
    "7132": "A-level Business",
    "7138": "A-level Business (New)",
    "7405": "A-level Chemistry",
    "7517": "A-level Computer Science",
    "7237": "A-level Dance",
    "7552": "A-level Design and Technology",
    "7562": "A-level Design and Technology (Alt)",
    "7262": "A-level Drama",
    "7136": "A-level Economics",
    "7702": "A-level English Language",
    "7707": "A-level English Language and Literature",
    "7712": "A-level English Literature A",
    "7717": "A-level English Literature B",
    "7447": "A-level Environmental Science",
    "7652": "A-level French",
    "7367": "A-level Further Mathematics",
    "7037": "A-level Geography",
    "7662": "A-level German",
    "7677": "A-level Hebrew (Biblical)",
    "7672": "A-level Hebrew (Modern)",
    "7042": "A-level History",
    "7162": "A-level Law",
    "7357": "A-level Mathematics",
    "7572": "A-level Media Studies",
    "7272": "A-level Music",
    "7682": "A-level Panjabi",
    "7172": "A-level Philosophy",
    "7582": "A-level Physical Education",
    "7408": "A-level Physics",
    "7687": "A-level Polish",
    "7152": "A-level Politics",
    "7182": "A-level Psychology",
    "7062": "A-level Religious Studies",
    "7192": "A-level Sociology",
    "7692": "A-level Spanish",

    # — GCSE —
    "8464": "GCSE Combined Science: Trilogy",
    "8465": "GCSE Combined Science: Synergy",
    "8525": "GCSE Computer Science",
    "8236": "GCSE Dance",
    "8552": "GCSE Design and Technology",
    "8261": "GCSE Drama",
    "8136": "GCSE Economics",
    "8700": "GCSE English Language",
    "8702": "GCSE English Literature",
    "8585": "GCSE Food Preparation and Nutrition",
    "8652": "GCSE French (2026 onwards)",
    "8658": "GCSE French (last sitting)",
    "8035": "GCSE Geography",
    "8662": "GCSE German (2026 onwards)",
    "8668": "GCSE German (last sitting)",
    "8678": "GCSE Hebrew (Modern)",
    "8145": "GCSE History",
    "8633": "GCSE Italian",
    "8300": "GCSE Mathematics",
    "8572": "GCSE Media Studies",
    "8271": "GCSE Music",
    "8683": "GCSE Panjabi",
    "8582": "GCSE Physical Education",
    "8463": "GCSE Physics",
    "8688": "GCSE Polish",
    "8182": "GCSE Psychology",
    "8061": "GCSE Religious Studies (Spec A)",
    "8062": "GCSE Religious Studies (Spec B)",
    "8063": "GCSE Religious Studies (Spec C)",
    "8192": "GCSE Sociology",
    "8692": "GCSE Spanish (2026 onwards)",
    "8698": "GCSE Spanish (last sitting)",
    "8382": "GCSE Statistics",
    "8648": "GCSE Urdu",

    # — Other AQA certificates —
    "8365": "AQA Certificate Level 2 Further Mathematics",
    "1350": "AQA Level 3 Mathematical Studies (Core Maths)",
    "7993": "AQA Level 3 Extended Project Qualification"
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
