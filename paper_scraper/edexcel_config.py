ALGOLIA_ENDPOINT = (
    "https://l639t95u5a-dsn.algolia.net"
    "/1/indexes/qualifications-uk_LIVE_master-content/query"
)
ALGOLIA_APP_ID = "L639T95U5A"
ALGOLIA_API_KEY = "f79c7a8352e9ffbdaec387bf43612ee6"
BASE_URL = "https://qualifications.pearson.com"

# Maps the spec_code → Pearson taxonomy spec identifier.
# The taxonomy code is what appears in category:"Pearson-UK:Specification-Code/{code}".
#
# Notes:
# - 9MA0/9FM0 share one Algolia code ("maths-2017-as-al"); spec_prefix disambiguates by filename.
# - 1BI0/1CH0/1PH0/1SC0 share "gcse16-science"; spec_prefix disambiguates by filename prefix.
# - 7M20 is a Level 2 qualification (not technically GCSE) but i am treating it the same way.
# - 1RS0 (GCSE Religious Studies) is omitted: Pearson publishes it as two separate Algolia specs
#   and I don't know what to do about it.
#   Add two explicit entries if RS coverage is needed.
# - 9CS0 (A-level Computer Science) is omitted: no past-paper PDFs found in the Algolia index.
SPECS = {

    # =========================
    # A-LEVEL
    # =========================

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
            "1": "Advanced Inorganic and Physical Chemistry",
            "2": "Advanced Organic and Physical Chemistry",
            "3": "General and Practical Principles in Chemistry",
        },
    },
    "9BI0": {
        "subject": "A-level Biology B",
        "algolia_code": "al15-biology-b",
        "spec_prefix": "9BI0",
        "paper_names": {
            "1": "Advanced Biochemistry, Microbiology and Genetics",
            "2": "Advanced Physiology, Evolution and Ecology",
            "3": "General and Practical Principles in Biology",
        },
    },
    "9BN0": {
        "subject": "A-level Biology A (Salters-Nuffield)",
        "algolia_code": "al15-biology-a",
        "spec_prefix": "9BN0",
        "paper_names": {
            "1": "Advanced Biochemistry, Microbiology and Genetics",
            "2": "Advanced Physiology, Evolution and Ecology",
            "3": "General and Practical Principles in Biology",
        },
    },
    "9EC0": {
        "subject": "A-level Economics A",
        "algolia_code": "al15-economics-a",
        "spec_prefix": "9EC0",
        "paper_names": {
            "1": "Markets and Business Behaviour",
            "2": "The National and Global Economy",
            "3": "Microeconomics and Macroeconomics",
        },
    },
    "9EB0": {
        "subject": "A-level Economics B",
        "algolia_code": "al15-economics-b",
        "spec_prefix": "9EB0",
        "paper_names": {
            "1": "Markets, Consumers and Firms",
            "2": "The Wider Economic Environment",
            "3": "Microeconomics and Macroeconomics",
        },
    },
    "9BS0": {
        "subject": "A-level Business",
        "algolia_code": "al15-business",
        "spec_prefix": "9BS0",
        "paper_names": {
            "1": "Marketing, People and Global Businesses",
            "2": "Business Activities, Decisions and Strategy",
            "3": "Investigating Business in a Competitive Environment",
        },
    },
    "9PS0": {
        "subject": "A-level Psychology",
        "algolia_code": "al15-psychology",
        "spec_prefix": "9PS0",
        "paper_names": {
            "1": "Social and Cognitive Psychology",
            "2": "Biological Psychology, Learning Theories and Development",
            "3": "Applications of Psychology",
        },
    },
    "9GE0": {
        "subject": "A-level Geography",
        "algolia_code": "al16-geography",
        "spec_prefix": "9GE0",
        "paper_names": {
            "1": "Dynamic Landscapes and Physical Systems",
            "2": "Dynamic Places and Human Systems",
            "3": "Synoptic Investigation of a Geographical Issue",
        },
    },
    "9HI0": {
        "subject": "A-level History",
        "algolia_code": "al15-history",
        "spec_prefix": "9HI0",
        "paper_names": {
            "1": "Breadth Study with Interpretations",
            "2": "Depth Study",
            "3": "Themes in Breadth with Aspects in Depth",
        },
    },
    "9EN0": {
        "subject": "A-level English Language",
        "algolia_code": "al15-eng-lang",
        "spec_prefix": "9EN0",
    },
    "9ET0": {
        "subject": "A-level English Literature",
        "algolia_code": "al15-eng-lit",
        "spec_prefix": "9ET0",
    },
    "9EL0": {
        "subject": "A-level English Language and Literature",
        "algolia_code": "al15-eng-langlit",
        "spec_prefix": "9EL0",
    },
    "9PL0": {
        "subject": "A-level Politics",
        "algolia_code": "al17-politics",
        "spec_prefix": "9PL0",
        "paper_names": {
            "1": "UK Politics and Core Political Ideas",
            "2": "UK Government and Non-core Political Ideas",
            "3": "Comparative Politics",
        },
    },
    "9RS0": {
        "subject": "A-level Religious Studies",
        "algolia_code": "al16-religiousstudies",
        "spec_prefix": "9RS0",
        "paper_names": {
            "1": "Philosophy of Religion",
            "2": "Religion and Ethics",
            "3": "New Testament Studies",
        },
    },
    "9PE0": {
        "subject": "A-level Physical Education",
        "algolia_code": "al16-physicaleducation",
        "spec_prefix": "9PE0",
        "paper_names": {
            "1": "Scientific Principles of Physical Education",
            "2": "Psychological and Social Principles of Physical Education",
        },
    },
    "9MU0": {
        "subject": "A-level Music",
        "algolia_code": "al16-music",
        "spec_prefix": "9MU0",
        "paper_names": {
            "3": "Appraising",
        },
    },
    "9DR0": {
        "subject": "A-level Drama and Theatre",
        "algolia_code": "al16-dramatheatre",
        "spec_prefix": "9DR0",
        "paper_names": {
            "3": "Theatre Makers in Practice",
        },
    },
    # 9FA0 and 9AD0 share the same Algolia code ("al15-artdes"); spec_prefix disambiguates by filename.
    "9FA0": {"subject": "A-level Art and Design (Fine Art)",             "algolia_code": "al15-artdes",             "spec_prefix": "9FA0"},
    "9AD0": {"subject": "A-level Art and Design (Art, Craft and Design)","algolia_code": "al15-artdes",             "spec_prefix": "9AD0"},
    # 9PY0 (Photography): NOT FOUND in Algolia index.
    "9DT0": {
        "subject": "A-level Design and Technology",
        "algolia_code": "al17-designtech-proddesign",
        "spec_prefix": "9DT0",
        "paper_names": {
            "1": "Core Technical Principles",
            "2": "Specialist Technical Principles",
        },
    },
    # 9LA0 (Law): NOT FOUND in Algolia index.
    "9FR0": {"subject": "A-level French",  "algolia_code": "al16-french",  "spec_prefix": "9FR0"},
    "9GN0": {"subject": "A-level German",  "algolia_code": "al16-german",  "spec_prefix": "9GN0"},
    "9SP0": {"subject": "A-level Spanish", "algolia_code": "al16-spanish", "spec_prefix": "9SP0"},
    # 9IT0 (Italian): NOT FOUND in Algolia index.
    "9RU0": {"subject": "A-level Russian", "algolia_code": "al17-russian", "spec_prefix": "9RU0"},
    "9CN0": {"subject": "A-level Chinese", "algolia_code": "al17-chinese", "spec_prefix": "9CN0"},

    # =========================
    # GCSE
    # =========================

    "1MA1": {"subject": "GCSE Mathematics",        "algolia_code": "gcse15-maths",           "spec_prefix": "1MA1"},
    "1ST0": {"subject": "GCSE Statistics",         "algolia_code": "gcse17-stat",            "spec_prefix": "1ST0"},
    "7M20": {"subject": "Extended Certificate in Mathematics", "algolia_code": "l2-extd-maths-cert", "spec_prefix": "7M20"},

    "1BI0": {"subject": "GCSE Biology",            "algolia_code": "gcse16-science",         "spec_prefix": "1BI0"},
    "1CH0": {"subject": "GCSE Chemistry",          "algolia_code": "gcse16-science",         "spec_prefix": "1CH0"},
    "1PH0": {"subject": "GCSE Physics",            "algolia_code": "gcse16-science",         "spec_prefix": "1PH0"},
    "1SC0": {"subject": "GCSE Combined Science",   "algolia_code": "gcse16-science",         "spec_prefix": "1SC0"},

    "1BS0": {"subject": "GCSE Business",           "algolia_code": "gcse17-business",        "spec_prefix": "1BS0"},
    "1CP2": {"subject": "GCSE Computer Science",   "algolia_code": "gcse20-computerscience", "spec_prefix": "1CP2"},

    "1EN0": {"subject": "GCSE English Language",   "algolia_code": "gcse15-englang",         "spec_prefix": "1EN0"},
    "1ET0": {"subject": "GCSE English Literature", "algolia_code": "gcse15-englit",          "spec_prefix": "1ET0"},

    "1GA0": {"subject": "GCSE Geography A",        "algolia_code": "gcse16-geography-a",     "spec_prefix": "1GA0"},
    "1GB0": {"subject": "GCSE Geography B",        "algolia_code": "gcse16-geography-b",     "spec_prefix": "1GB0"},
    "1HI0": {"subject": "GCSE History",            "algolia_code": "gcse16-history",         "spec_prefix": "1HI0"},

    "1PS0": {"subject": "GCSE Psychology",         "algolia_code": "gcse17-psychology",      "spec_prefix": "1PS0"},

    "1DR0": {"subject": "GCSE Drama",               "algolia_code": "gcse16-drama",              "spec_prefix": "1DR0"},
    # 1DA0 (Dance): NOT FOUND in Algolia index.
    "1MU0": {"subject": "GCSE Music",               "algolia_code": "gcse16-music",              "spec_prefix": "1MU0"},
    # 1FA0 (Fine Art): NOT FOUND in Algolia index.
    # 1PY0 (Photography): NOT FOUND in Algolia index.
    "1PE0": {"subject": "GCSE Physical Education",  "algolia_code": "gcse16-physicaleducation",  "spec_prefix": "1PE0"},
    "1DT0": {"subject": "GCSE Design and Technology","algolia_code": "gcse17-designtechnology",  "spec_prefix": "1DT0"},
    "1FR0": {"subject": "GCSE French",              "algolia_code": "gcse-16-french",            "spec_prefix": "1FR0"},
    "1GN0": {"subject": "GCSE German",              "algolia_code": "gcse16-german",             "spec_prefix": "1GN0"},
    "1SP0": {"subject": "GCSE Spanish",             "algolia_code": "gcse16-spanish",            "spec_prefix": "1SP0"},
    # 1IT0 (Italian): NOT FOUND in Algolia index.
    "1RU0": {"subject": "GCSE Russian",             "algolia_code": "gcse17-russian",            "spec_prefix": "1RU0"},
    "1CN0": {"subject": "GCSE Chinese",             "algolia_code": "gcse17-chinese",            "spec_prefix": "1CN0"},
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
from paper_scraper import compute_max_year
MAX_YEAR = compute_max_year()
