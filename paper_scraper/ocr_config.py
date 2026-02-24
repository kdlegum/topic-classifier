BASE_URL = "https://www.ocr.org.uk"
LEVELS_ENDPOINT = "https://www.ocr.org.uk/resource/getlevels/"
FILTER_ENDPOINT = "https://www.ocr.org.uk/resource/filterresourcesbysubject/"

# Fixed params for the filter endpoint
TEMPLATE_ID = 383453
RESULT_HEADER = "Documents"
ERROR_MESSAGE = "Sorry there are currently no past paper materials for this qualification."
RESOURCE_TYPES = ["Past papers", "Practice materials"]

# Specs: keyed by A-level spec code (the H-prefixed one)
# qualification_value: OCR's internal numeric ID for the subject (shared by AS + A Level)
# level: "A Level" or "AS Level"
# page_id: Optional TCM content ID of the qual's past-papers page (e.g. "tcm:33-526922-64").
#          Leave empty to omit it — the API may still respond without it.
SPECS = {
    "H240": {
        "subject": "Mathematics A (A Level)",
        "qualification_value": 308647,
        "level": "A Level",
        "page_id": "",
    },
    "H640": {
        "subject": "Mathematics B MEI (A Level)",
        "qualification_value": 308649,
        "level": "A Level",
        "page_id": "tcm:33-526922-64",
    },
    "H245": {
        "subject": "Further Mathematics A (A Level)",
        "qualification_value": 308648,
        "level": "A Level",
        "page_id": "",
    },
    "H645": {
        "subject": "Further Mathematics B MEI (A Level)",
        "qualification_value": 308650,
        "level": "A Level",
        "page_id": "",
    },
    "H420": {
        "subject": "Biology A (A Level)",
        "qualification_value": 168469,
        "level": "A Level",
        "page_id": "",
    },
    "H422": {
        "subject": "Biology B Advancing Biology (A Level)",
        "qualification_value": 168478,
        "level": "A Level",
        "page_id": "",
    },
    "H432": {
        "subject": "Chemistry A (A Level)",
        "qualification_value": 168530,
        "level": "A Level",
        "page_id": "",
    },
    "H433": {
        "subject": "Chemistry B Salters (A Level)",
        "qualification_value": 168531,
        "level": "A Level",
        "page_id": "",
    },
    "H556": {
        "subject": "Physics A (A Level)",
        "qualification_value": 168534,
        "level": "A Level",
        "page_id": "",
    },
    "H557": {
        "subject": "Physics B Advancing Physics (A Level)",
        "qualification_value": 168535,
        "level": "A Level",
        "page_id": "",
    },
    "H446": {
        "subject": "Computer Science (A Level)",
        "qualification_value": 168479,
        "level": "A Level",
        "page_id": "",
    },
    "H460": {
        "subject": "Economics (A Level)",
        "qualification_value": 531790,
        "level": "A Level",
        "page_id": "",
    },
    "H481": {
        "subject": "Geography (A Level)",
        "qualification_value": 222823,
        "level": "A Level",
        "page_id": "",
    },
    "H505": {
        "subject": "History A (A Level)",
        "qualification_value": 168541,
        "level": "A Level",
        "page_id": "",
    },
    "H431": {
        "subject": "Business (A Level)",
        "qualification_value": 168545,
        "level": "A Level",
        "page_id": "",
    },
    "H567": {
        "subject": "Psychology (A Level)",
        "qualification_value": 168546,
        "level": "A Level",
        "page_id": "",
    },
    "H580": {
        "subject": "Sociology (A Level)",
        "qualification_value": 168547,
        "level": "A Level",
        "page_id": "",
    },
    "H573": {
        "subject": "Religious Studies (A Level)",
        "qualification_value": 232443,
        "level": "A Level",
        "page_id": "",
    },
    # GCSE qualifications
    "J198": {
        "subject": "Ancient History (9-1)",
        "qualification_value": 313161,
        "level": "GCSE",
        "page_id": "",
    },
    "J170": {
        "subject": "Art and Design (9-1)",
        "qualification_value": 220480,
        "level": "GCSE",
        "page_id": "",
    },
    "J204": {
        "subject": "Business (9-1)",
        "qualification_value": 304083,
        "level": "GCSE",
        "page_id": "",
    },
    "J270": {
        "subject": "Citizenship Studies (9-1)",
        "qualification_value": 232413,
        "level": "GCSE",
        "page_id": "",
    },
    "J199": {
        "subject": "Classical Civilisation (9-1)",
        "qualification_value": 307261,
        "level": "GCSE",
        "page_id": "",
    },
    "J292": {
        "subject": "Classical Greek (9-1)",
        "qualification_value": 220689,
        "level": "GCSE",
        "page_id": "",
    },
    "J277": {
        "subject": "Computer Science (9-1)",
        "qualification_value": 552495,
        "level": "GCSE",
        "page_id": "",
    },
    "J310": {
        "subject": "Design and Technology (9-1)",
        "qualification_value": 304091,
        "level": "GCSE",
        "page_id": "",
    },
    "J316": {
        "subject": "Drama (9-1)",
        "qualification_value": 232395,
        "level": "GCSE",
        "page_id": "",
    },
    "J205": {
        "subject": "Economics (9-1)",
        "qualification_value": 306046,
        "level": "GCSE",
        "page_id": "",
    },
    "J351": {
        "subject": "English Language (9-1)",
        "qualification_value": 168444,
        "level": "GCSE",
        "page_id": "",
    },
    "J352": {
        "subject": "English Literature (9-1)",
        "qualification_value": 168448,
        "level": "GCSE",
        "page_id": "",
    },
    "J309": {
        "subject": "Food Preparation and Nutrition (9-1)",
        "qualification_value": 232201,
        "level": "GCSE",
        "page_id": "",
    },
    "J247": {
        "subject": "Gateway Science Suite - Biology A (9-1)",
        "qualification_value": 231296,
        "level": "GCSE",
        "page_id": "",
    },
    "J248": {
        "subject": "Gateway Science Suite - Chemistry A (9-1)",
        "qualification_value": 231304,
        "level": "GCSE",
        "page_id": "",
    },
    "J250": {
        "subject": "Gateway Science Suite - Combined Science A (9-1)",
        "qualification_value": 231309,
        "level": "GCSE",
        "page_id": "",
    },
    "J249": {
        "subject": "Gateway Science Suite - Physics A (9-1)",
        "qualification_value": 231307,
        "level": "GCSE",
        "page_id": "",
    },
    "J383": {
        "subject": "Geography A (Geographical Themes) (9-1)",
        "qualification_value": 207170,
        "level": "GCSE",
        "page_id": "",
    },
    "J384": {
        "subject": "Geography B (Geography for Enquiring Minds) (9-1)",
        "qualification_value": 207171,
        "level": "GCSE",
        "page_id": "",
    },
    "J410": {
        "subject": "History A (Explaining the Modern World) (9-1)",
        "qualification_value": 206636,
        "level": "GCSE",
        "page_id": "",
    },
    "J411": {
        "subject": "History B (Schools History Project) (9-1)",
        "qualification_value": 206883,
        "level": "GCSE",
        "page_id": "",
    },
    "J282": {
        "subject": "Latin (9-1)",
        "qualification_value": 220692,
        "level": "GCSE",
        "page_id": "",
    },
    "J560": {
        "subject": "Mathematics (9-1)",
        "qualification_value": 168037,
        "level": "GCSE",
        "page_id": "",
    },
    "J200": {
        "subject": "Media Studies (9-1)",
        "qualification_value": 687688,
        "level": "GCSE",
        "page_id": "",
    },
    "J536": {
        "subject": "Music (9-1)",
        "qualification_value": 214380,
        "level": "GCSE",
        "page_id": "",
    },
    "J587": {
        "subject": "Physical Education (9-1)",
        "qualification_value": 232393,
        "level": "GCSE",
        "page_id": "",
    },
    "J203": {
        "subject": "Psychology (9-1)",
        "qualification_value": 309310,
        "level": "GCSE",
        "page_id": "",
    },
    "J625": {
        "subject": "Religious Studies (9-1)",
        "qualification_value": 232406,
        "level": "GCSE",
        "page_id": "",
    },
    "J257": {
        "subject": "Twenty First Century Science Suite - Biology B (9-1)",
        "qualification_value": 231315,
        "level": "GCSE",
        "page_id": "",
    },
    "J258": {
        "subject": "Twenty First Century Science Suite - Chemistry B (9-1)",
        "qualification_value": 231342,
        "level": "GCSE",
        "page_id": "",
    },
    "J260": {
        "subject": "Twenty First Century Science Suite - Combined Science B (9-1)",
        "qualification_value": 231344,
        "level": "GCSE",
        "page_id": "",
    },
    "J259": {
        "subject": "Twenty First Century Science Suite - Physics B (9-1)",
        "qualification_value": 231343,
        "level": "GCSE",
        "page_id": "",
    },
}

# Document title keywords → internal paper_type code
DOC_TYPE_MAP = {
    "question paper": "QP",
    "mark scheme": "MS",
    "insert": "INSERT",
    "data sheet": "DATA",
    "data booklet": "DATA",
    "formula booklet": "FORMULA",
    "examiner report": "ER",
    "examiner's report": "ER",
}

KEEP_TYPES = {"QP", "MS"}

OUTPUT_DIR = "paper_scraper/papers/ocr"
METADATA_FILE = "paper_scraper/ocr_index.json"
DOWNLOAD_DELAY_S = 1.0
PAGE_DELAY_S = 0.5

# Papers from years after MAX_YEAR are skipped (still locked/unreleased).
from paper_scraper import compute_max_year
MAX_YEAR = compute_max_year()
