# Topic Tracker

Topic tracker classifies A Level and GCSE past papers against their exam board specifications to aid revision. Go to [topictracker.co.uk](topictracker.co.uk), upload a paper and mark it to get a breakdown of your strengths and weaknesses. 

## Overview

An ideal way to revise is to do past papers, mark yourself, and come back to questions that you got wrong in the past. You'd also want to match each question to the spec point that it was created from so that you can make sure you are able to do questions corresponding to every spec point from the official specification. However, realistically, this takes too much time and organisation for most people. The goal of this website is to have one place for all your past papers.

<table>
  <tr>
    <td><img src="https://github.com/user-attachments/assets/2f0ef017-fedb-4514-afb6-c9dc6573f8fe" width="100%"></td>
    <td><img src="https://github.com/user-attachments/assets/31905ffd-82dc-4a46-bb61-2c53a74209c5" width="100%"></td>
  </tr>
</table>

## Supported Specifications

Note that users can also add their own, custom specifications.

### GCSE Subjects

Additional Mathematics: OCR

Biology: AQA, Edexcel

Business: AQA, Edexcel

Chemistry: AQA, Edexcel

Combined Science (Trilogy): AQA

Combined Science: Edexcel

Computer Science (2027): AQA

Computer Science: AQA, Edexcel, OCR

Extended Mathematics Certificate: Edexcel

Further Mathematics: AQA

Geography A: Edexcel

Geography: AQA

Geography B: Edexcel

History A: OCR

History: AQA, Edexcel

History B: OCR

Mathematics: AQA, Edexcel, OCR

Physics: AQA, Edexcel

Religious Studies A: AQA

Statistics: Edexcel

### A Level Subjects

Mathematics: OCR, AQA, Edexcel

Physics: Edexcel, AQA

Further Mathematics B (MEI): OCR

Biology: AQA, OCR

Chemistry: AQA, Edexcel, OCR

Computer Science: AQA, OCR

Economics: AQA, Edexcel

Further Mathematics: AQA, Edexcel

## Tech Stack

- **Backend**: FastAPI (Python) REST API with PostgreSQL
- **Frontend**: SvelteKit (Svelte 5) with Supabase for auth
- **AI**: Sentence-Transformers (`all-MiniLM-L6-v2`) for semantic similarity; OlmOCR ot Gemini 2.0 Flash for question extraction from OCR markdown depending on availability.

## Running Locally

### Prerequisites

- Python 3.10+
- Node.js 18+
- `GOOGLE_API_KEY` environment variable (required for Gemini Flash PDF question extraction)

### Quickstart

```bash
cd Backend
pip install -r requirements.txt
nohup uvicorn main:app --reload > uvicorn.log 2>&1 &

cd ../frontend
npm install
npm run dev
```

After the first run, use `.\start.ps1` in PowerShell, or:

```bash
cd Backend
nohup uvicorn main:app --reload > uvicorn.log 2>&1 &

cd ../frontend
npm run dev
```

The API will be available at `http://127.0.0.1:8000`, and the dev server at `http://localhost:5173`.

## Paper Scraper

`paper_scraper/` is a standalone CLI tool for downloading past papers from AQA, Edexcel, and OCR. See [`paper_scraper/README.md`](paper_scraper/README.md) for full usage.

```bash
pip install uk-exam-paper-scraper

paper-scraper --board aqa --spec-code 7408 --dry-run
paper-scraper --board ocr --spec-code H240 --download
paper-scraper --board edexcel --spec-code 9MA0 --download
```
