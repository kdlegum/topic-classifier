# Topic Tracker

Exam paper analysis system that classifies exam questions by subject topics and subtopics using semantic similarity matching.

## Overview

Students upload exam papers (PDF or text) and the system automatically categorizes each question against exam board specifications (OCR, Edexcel). This helps identify weak areas and track revision progress.

Key capabilities:

- **AI classification** — each question is ranked against specification subtopics using sentence-transformer embeddings
- **PDF upload** — extract questions from scanned papers via OCR
- **Marking** — record marks per question and track scores across sessions
- **User corrections** — override AI predictions with the correct topic
- **Analytics** — visualize performance breakdowns by strand and topic
- **Authentication** — guest access with seamless migration to a Supabase account

## Architecture

- **Backend**: FastAPI (Python) REST API with PostgreSQL database, hosted on Supabase.
- **Frontend**: SvelteKit (Svelte 5) with Supabase authentication
- **AI**: Sentence-Transformers (`all-MiniLM-L6-v2`) for semantic similarity
- **PDF Processing**: olmOCR for PDF-to-Markdown conversion

## Directory Structure

```
Backend/            FastAPI server, database models, auth, classification logic
frontend/           SvelteKit frontend application
pdf_interpretation/ PDF OCR and markdown parsing pipeline
```

## How It Works

1. **Session creation** — user selects an exam board and subject, then submits questions (text input or PDF upload).
2. **Encoding** — questions are encoded using a Sentence-Transformer model.
3. **Classification** — cosine similarity is computed against all specification subtopics; the top-3 predictions are stored with confidence scores.
4. **Review** — results are displayed with topic breakdowns. Users can correct predictions and record marks.
5. **Analytics** — performance data is aggregated across sessions to highlight weak areas.

## Authentication

- **Guests**: UUID stored in localStorage, sent as `X-Guest-ID` header
- **Authenticated users**: Supabase JWT tokens sent as `Authorization: Bearer` header
- Guest sessions automatically migrate to the user's account on signup

## Database

PostgreSQL (`exam_app.db`) managed with SQLModel. Tables:

| Table | Purpose |
|---|---|
| `session` | Exam paper sessions |
| `question` | Individual questions within a session |
| `prediction` | AI topic predictions per question |
| `questionmark` | Mark allocations per question |
| `usercorrection` | User-submitted topic corrections |

The following tables store the data from specifications, including the text used for classification. In the future, users will be able to create and upload their own specifications, potentially with assistance of AI.

| Table | Purpose |
|---|---|
| `Specification` | Overall metadata for specifications |
| `Topic` | Individual topic within a specification |
| `Subtopic` | Individual subtopic within a topic |

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+

### Quickstart

In bash:

```bash
cd Backend
pip install -r requirements.txt
nohup uvicorn main:app --reload > uvicorn.log 2>&1 &

cd ../frontend
npm install
npm run dev
```

After the first time, you can use .\start.ps1 in windows powershell to start the servers, or:

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
| Backend | FastAPI, SQLModel, PostgreSQL |
| Frontend | SvelteKit (Svelte 5), Chart.js |
| AI | Sentence-Transformers (`all-MiniLM-L6-v2`) |
| Auth | Supabase |
| PDF | olmOCR |
