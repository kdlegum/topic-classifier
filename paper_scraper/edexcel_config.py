ALGOLIA_ENDPOINT = (
    "https://l639t95u5a-dsn.algolia.net"
    "/1/indexes/qualifications-uk_LIVE_master-content/query"
)
ALGOLIA_APP_ID = "L639T95U5A"
ALGOLIA_API_KEY = "f79c7a8352e9ffbdaec387bf43612ee6"
BASE_URL = "https://qualifications.pearson.com"

# Maps our internal spec_code → Pearson taxonomy spec identifier.
# The taxonomy code is what appears in category:"Pearson-UK:Specification-Code/{code}".
#
# Notes:
# - 9MA0/9FM0 share one Algolia code ("maths-2017-as-al"); spec_prefix disambiguates by filename.
# - 1BI0/1CH0/1PH0/1SC0 share "gcse16-science"; spec_prefix disambiguates by filename prefix.
# - 7M20 is a Level 2 qualification (not technically GCSE) but treated the same way.
SPECS = {
    # A-level
    "9MA0": {
        "subject": "A-level Mathematics",
        "algolia_code": "maths-2017-as-al",
        "spec_prefix": "9MA0",
        "paper_names": {
            "1": "Pure Mathematics 1",
            "2": "Pure Mathematics 2",
            "3": "Statistics and Mechanics",
        },
    },
    "9FM0": {
        "subject": "A-level Further Mathematics",
        "algolia_code": "maths-2017-as-al",
        "spec_prefix": "9FM0",
        "paper_names": {
            "1": "Core Pure Mathematics 1",
            "2": "Core Pure Mathematics 2",
        },
    },
    "9PH0": {
        "subject": "A-level Physics",
        "algolia_code": "al15-physics",
        "spec_prefix": "9PH0",
        "paper_names": {
            "1": "Advanced Physics I",
            "2": "Advanced Physics II",
            "3": "General and Practical Principles in Physics",
        },
    },
    "9CH0": {
        "subject": "A-level Chemistry",
        "algolia_code": "al15-chemistry",
        "spec_prefix": "9CH0",
        "paper_names": {
            "1": "Core Inorganic and Physical Chemistry",
            "2": "Core Organic and Physical Chemistry",
            "3": "General and Practical Principles in Chemistry",
        },
    },
    "9EC0": {
        "subject": "A-level Economics",
        "algolia_code": "al15-economics-a",
        "spec_prefix": "9EC0",
        "paper_names": {
            "1": "Markets and Business Behaviour",
            "2": "The National and Global Economy",
            "3": "Microeconomics and Macroeconomics",
        },
    },
    # GCSE (papers are numbered only — no subtitles)
    "1BI0": {"subject": "GCSE Biology",                        "algolia_code": "gcse16-science",         "spec_prefix": "1BI0"},
    "1BS0": {"subject": "GCSE Business",                       "algolia_code": "gcse17-business",        "spec_prefix": "1BS0"},
    "1CH0": {"subject": "GCSE Chemistry",                      "algolia_code": "gcse16-science",         "spec_prefix": "1CH0"},
    "1SC0": {"subject": "GCSE Combined Science",               "algolia_code": "gcse16-science",         "spec_prefix": "1SC0"},
    "1CP2": {"subject": "GCSE Computer Science",               "algolia_code": "gcse20-computerscience", "spec_prefix": "1CP2"},
    "7M20": {"subject": "Extended Certificate in Mathematics", "algolia_code": "l2-extd-maths-cert",     "spec_prefix": "7M20"},
    "1GA0": {"subject": "GCSE Geography A",                    "algolia_code": "gcse16-geography-a",     "spec_prefix": "1GA0"},
    "1GB0": {"subject": "GCSE Geography B",                    "algolia_code": "gcse16-geography-b",     "spec_prefix": "1GB0"},
    "1HI0": {"subject": "GCSE History",                        "algolia_code": "gcse16-history",         "spec_prefix": "1HI0"},
    "1MA1": {"subject": "GCSE Mathematics",                    "algolia_code": "gcse15-maths",           "spec_prefix": "1MA1"},
    "1PH0": {"subject": "GCSE Physics",                        "algolia_code": "gcse16-science",         "spec_prefix": "1PH0"},
    "1ST0": {"subject": "GCSE Statistics",                     "algolia_code": "gcse17-stat",            "spec_prefix": "1ST0"},
}

# Pearson document-type taxonomy value → internal paper_type code
DOC_TYPE_MAP = {
    "Question-paper": "QP",
    "Mark-scheme": "MS",
    "Past-question-paper-and-mark-scheme": "QP",  # combined PDF, treat as QP
    "Examiner-report": "ER",
    "Data-files": "DATA",
}

# Paper types to keep (all others are silently skipped)
KEEP_TYPES = {"QP", "MS"}

OUTPUT_DIR = "paper_scraper/papers/edexcel"
METADATA_FILE = "paper_scraper/edexcel_index.json"
DOWNLOAD_DELAY_S = 1.0
PAGE_DELAY_S = 0.5

# Papers from years after MAX_YEAR are skipped (typically still locked/unreleased).
# Raise this once a series becomes publicly available.
MAX_YEAR = 2024
