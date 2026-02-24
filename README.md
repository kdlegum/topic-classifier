# Topic Tracker

Exam paper analysis system that classifies exam questions by subject topics and subtopics using semantic similarity matching.

## Overview

Students upload exam papers (PDF or text) and the system automatically categorizes each question against exam board specifications (OCR, Edexcel, AQA). This helps identify weak areas and track revision progress. Past papers from official exam board sources can also be downloaded directly using the bundled scraper tool.

Key capabilities:

- **AI classification** — each question is ranked against specification subtopics using sentence-transformer embeddings
- **PDF upload** — extract questions from scanned papers via OCR and Gemini Flash
- **Marking** — record marks per question and track scores across sessions
- **User corrections** — override AI predictions with the correct topic
- **Optional modules** — filter classification to selected strands for modular specifications (e.g. OCR Further Maths H645)
- **Revision** — flashcard-style revision queue built from questions scored below full marks
- **Analytics** — visualize performance breakdowns by strand and topic
- **Past paper downloads** — scrape and download past papers and mark schemes from AQA, Edexcel, and OCR official sources
- **Authentication** — guest access with seamless migration to a Supabase account

## Architecture

- **Backend**: FastAPI (Python) REST API with SQLite (local) / PostgreSQL (production)
- **Frontend**: SvelteKit (Svelte 5) with Supabase authentication
- **AI**: Sentence-Transformers (`all-MiniLM-L6-v2`) for semantic similarity; Gemini 2.0 Flash for question extraction from OCR markdown
- **PDF Processing**: olmOCR for PDF-to-Markdown conversion

## Directory Structure

```
Backend/            FastAPI server, database models, auth, classification logic
frontend/           SvelteKit frontend application
pdf_interpretation/ PDF OCR and markdown parsing pipeline
paper_scraper/      CLI tool to download past papers from AQA, Edexcel, and OCR
spec_generation/    Scripts and data for building exam specification indexes
```

## How It Works

1. **Session creation** — user selects an exam board and subject, then submits questions (text input or PDF upload).
2. **Encoding** — questions are encoded using a Sentence-Transformer model.
3. **Classification** — cosine similarity is computed against all specification subtopics; the top-3 predictions are stored with confidence scores.
4. **Review** — results are displayed with topic breakdowns. Users can correct predictions and record marks.
5. **Analytics** — performance data is aggregated across sessions to highlight weak areas.

## Revision

The revision tab (`/revision`) surfaces questions that haven't been answered correctly yet as a flashcard-style queue.

- **Revision pool** — any question scored below full marks in a session is automatically added to the pool.
- **Flashcard UI** — one question is shown at a time with an animated card-stack behind it indicating remaining questions.
- **Self-grading** — after attempting the question, the user enters their mark. Full marks removes it from the pool; a partial score keeps it in for next time.
- **PDF access** — the original paper PDF and mark scheme can be downloaded directly from the card, and scanned questions can be viewed in context.
- **Spec filter** — the pool can be filtered to a single specification.
- **Manual removal** — questions can be removed from the pool without submitting a score.

## Authentication

- **Guests**: UUID stored in localStorage, sent as `X-Guest-ID` header
- **Authenticated users**: Supabase JWT tokens sent as `Authorization: Bearer` header
- Guest sessions automatically migrate to the user's account on signup

## Database

SQLite locally (`exam_app.db`), PostgreSQL in production (via `DATABASE_URL` env var), managed with SQLModel.

User data tables:

| Table | Purpose |
|---|---|
| `session` | Exam paper sessions |
| `question` | Individual questions within a session |
| `prediction` | AI topic predictions per question |
| `questionmark` | Mark allocations per question |
| `usercorrection` | User-submitted topic corrections |
| `usermoduleselection` | Selected strands per user per specification |
| `sessionstrand` | Strands associated with a session |

Specification tables (seeded from `spec_generation/aleveltopics.json`):

| Table | Purpose |
|---|---|
| `Specification` | Overall metadata for specifications |
| `Topic` | Individual topic within a specification |
| `Subtopic` | Individual subtopic within a topic |

## Getting Started

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

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, SQLModel, SQLite / PostgreSQL |
| Frontend | SvelteKit (Svelte 5), Chart.js |
| AI | Sentence-Transformers (`all-MiniLM-L6-v2`), Gemini 2.0 Flash |
| Auth | Supabase |
| PDF | olmOCR |

## Paper Scraper

`paper_scraper/` is a standalone CLI tool for downloading past papers from AQA, Edexcel, and OCR. See [`paper_scraper/README.md`](paper_scraper/README.md) for full usage.

```bash
pip install uk-exam-paper-scraper

paper-scraper --board aqa --spec-code 7408 --dry-run
paper-scraper --board ocr --spec-code H240 --download
paper-scraper --board edexcel --spec-code 9MA0 --download
```
