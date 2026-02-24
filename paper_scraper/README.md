# uk-exam-paper-scraper

Download AQA, Edexcel/Pearson, and OCR A-Level and GCSE past papers and mark schemes from official sources — no browser required.

> **Disclaimer:** Past paper PDFs are copyright of their respective exam boards. This tool is for personal educational use only. Ensure your use complies with each board's terms of service before redistributing downloaded files.

## Installation

```bash
pip install uk-exam-paper-scraper
```

Requires Python 3.9+.

## Quick Start

```bash
# AQA — download all configured specs
paper-scraper --board aqa

# Edexcel — build a metadata index (no download by default)
paper-scraper --board edexcel --all

# OCR — scrape a single spec
paper-scraper --board ocr --spec-code H240
```

## Usage

### AQA

```
paper-scraper --board aqa [--spec-code CODE] [--dry-run]
```

| Flag | Description |
|------|-------------|
| `--spec-code CODE` | Scrape a single spec (e.g. `7357` for A-level Maths). Defaults to all configured specs. |
| `--dry-run` | List discovered papers without downloading anything. |

AQA papers are downloaded by default. Files are saved under `paper_scraper/papers/{spec_code}/{year}/{series}/`.

**Example — preview A-level Physics papers:**
```bash
paper-scraper --board aqa --spec-code 7408 --dry-run
```

### Edexcel / Pearson

```
paper-scraper --board edexcel [--spec-code CODE] [--all] [--dry-run] [--download]
```

| Flag | Description |
|------|-------------|
| `--spec-code CODE` | Scrape a single spec (e.g. `9MA0` for A-level Maths). |
| `--all` | Explicitly scrape all configured specs. |
| `--dry-run` | List discovered papers without writing anything. |
| `--download` | Download PDFs (default behaviour is to build the metadata index only). |

**Example — download GCSE Maths papers:**
```bash
paper-scraper --board edexcel --spec-code 1MA1 --download
```

### OCR

```
paper-scraper --board ocr [--spec-code CODE] [--all] [--dry-run] [--download]
```

| Flag | Description |
|------|-------------|
| `--spec-code CODE` | Scrape a single spec (e.g. `H240` for A-level Maths A). |
| `--all` | Explicitly scrape all configured specs. |
| `--dry-run` | List discovered papers without writing anything. |
| `--download` | Download PDFs (default behaviour is to build the metadata index only). |

**Example — index all OCR specs without downloading:**
```bash
paper-scraper --board ocr --all
```

## Output

### PDF files

```
paper_scraper/papers/
  {spec_code}/
    {year}/
      {series}/
        AQA-73671-QP-JUN23.pdf
        AQA-73671-MS-JUN23.pdf
        ...
```

### Metadata index (JSON)

Each board writes a JSON index file:

| Board | File |
|-------|------|
| AQA | `paper_scraper/index.json` |
| Edexcel | `paper_scraper/edexcel_index.json` |
| OCR | `paper_scraper/ocr_index.json` |

Each entry contains:

```json
{
  "content_id": "sample-papers-and-mark-schemes.2023.june.AQA-73671-QP-JUN23_PDF",
  "spec_code": "7357",
  "subject": "A-level Mathematics",
  "year": 2023,
  "series": "june",
  "paper_type": "QP",
  "paper_number": "1",
  "paper_name": "Pure",
  "tier": null,
  "filename": "AQA-73671-QP-JUN23.pdf",
  "local_path": "paper_scraper/papers/7357/2023/june/AQA-73671-QP-JUN23.pdf",
  "source_url": "https://www.aqa.org.uk/files/...",
  "file_size_kb": 412.5,
  "scraped_at": "2025-06-01T10:00:00+00:00"
}
```

`paper_type` is one of: `QP` (question paper) or `MS` (mark scheme).

## Supported Specifications

### AQA

Covers all major A-level and GCSE subjects, including:

- **Sciences:** Biology (7402), Chemistry (7405), Physics (7408), Combined Science (8464/8465)
- **Maths:** Mathematics (7357), Further Mathematics (7367), GCSE Mathematics (8300)
- **Humanities:** History (7042), Geography (7037), English Literature A/B (7712/7717)
- **Languages:** French (7652), German (7662), Spanish (7692), and more
- **Other:** Psychology (7182), Sociology (7192), Computer Science (7517), Economics (7136), and many more

Run `paper-scraper --board aqa --dry-run` to see the full list.

### Edexcel / Pearson

Covers major A-level and GCSE subjects, including:

- **Sciences:** Biology A/B (9BI0/9BN0), Chemistry (9CH0), Physics (9PH0), GCSE sciences (1BI0, 1CH0, 1PH0, 1SC0)
- **Maths:** Mathematics (9MA0), Further Mathematics (9FM0), GCSE Mathematics (1MA1)
- **Humanities:** History (9HI0), Geography (9GE0), Economics A/B (9EC0/9EB0)
- **Languages:** French (9FR0), German (9GN0), Spanish (9SP0), Russian (9RU0), Chinese (9CN0)
- **Other:** Psychology (9PS0), Business (9BS0), Politics (9PL0), and more

### OCR

Covers major A-level and GCSE subjects, including:

- **Maths:** Mathematics A (H240), Mathematics B MEI (H640), Further Mathematics A/B (H245/H645)
- **Sciences:** Biology A/B (H420/H422), Chemistry A/B (H432/H433), Physics A/B (H556/H557)
- **Humanities:** History A (H505), Geography (H481), Economics (H460), Religious Studies (H573)
- **GCSE sciences:** Gateway Science (J247–J250), Twenty First Century Science (J257–J260)
- **Other:** Computer Science (H446), Psychology (H567), Sociology (H580), and more

## How It Works

Each board has an undocumented but public API. Here is a brief documentation of each but please do NOT hammer their servers. 

### AQA

AQA's past-papers page is powered by a JSON search API:

```
GET https://www.aqa.org.uk/api/search
    ?type=aqaResource
    &scope=findPastPapers
    &specCode={code}
    &page={n}
    &limit=100
    ...
```

The response contains a `results` array and a `hits` total. The scraper paginates until all results are collected. Each result's `contentId` field encodes the year, exam series, and filename in dot-separated segments (e.g. `sample-papers-and-mark-schemes.2023.june.AQA-73671-QP-JUN23_PDF`). The download URL is constructed as `https://www.aqa.org.uk/files/{contentId}`.

### Edexcel / Pearson

Pearson's qualifications site is backed by [Algolia](https://www.algolia.com/). The scraper POSTs directly to the Algolia query endpoint using a public read-only API key embedded in the site's JavaScript:

```
POST https://l639t95u5a-dsn.algolia.net/1/indexes/qualifications-uk_LIVE_master-content/query
{
  "params": "query=&filters=category:\"Pearson-UK:Specification-Code/{algolia_code}\"&hitsPerPage=1000"
}
```

Each Algolia hit carries a structured category taxonomy with fields for document type (`Pearson-UK:Document-Type/Question-paper`), exam series (`Pearson-UK:Exam-Series/June-2023`), and unit/paper number (`Pearson-UK:Unit/Paper-1H`). The tier (Higher/Foundation) is encoded as a suffix on the unit value.

The complication is that Algolia's taxonomy codes don't match the published spec codes: for example, both `9MA0` (A-level Maths) and `9FM0` (Further Maths) share the Algolia code `maths-2017-as-al`, and are distinguished by filename prefix. These mappings have to be discovered manually — see [Adding New Edexcel Specs](#adding-new-edexcel-specs) below.

### OCR

OCR's site uses two jQuery AJAX endpoints:

**Step 1** — confirm available qualification levels:
```
POST https://www.ocr.org.uk/resource/getlevels/
Body: qualification={qualification_value}
```
Returns a JSON list of available level strings (e.g. `"A Level"`, `"AS Level"`).

**Step 2** — fetch resource HTML for that level:
```
POST https://www.ocr.org.uk/resource/filterresourcesbysubject/
Body: qualification={value}&level={level}&resourcetypes[0]=Past+papers&...
```
Returns an HTML fragment (can take ~10 seconds) containing an accordion-style list of all past paper links for that qualification. The scraper parses this with BeautifulSoup, extracting PDF links, titles, unit codes, and file sizes from the nested `h4`/`ul.resource-list` structure.

The `qualification_value` is OCR's internal numeric ID for a subject (e.g. `308647` for Maths A), which is unrelated to the published spec code (`H240`). These are hard-coded in `ocr_config.SPECS`.

## Adding New Edexcel Specs

Edexcel's site is backed by Algolia. Each spec requires an internal Algolia code that isn't published. Use the bundled discovery script to find codes for specs not already in the config:

```bash
python -m paper_scraper._find_algolia_codes
```

Edit `SEARCHES` at the top of that file to add the spec codes you want to look up. It prints the Algolia taxonomy code for each one, which you can then add to `edexcel_config.SPECS`.

## Rate Limiting

The scrapers include built-in delays between requests (1–1.5 s between pages, 1 s between downloads) to avoid hammering exam board servers. Please do not reduce these.

## Dependencies

- `requests` — HTTP requests
- `beautifulsoup4` — HTML parsing (OCR scraper)
