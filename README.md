# Exam Paper AI Classifier

## Overview

**THIS PROJECT IS STILL IN ITS VERY EARLY STAGES**

This project is a web app that helps students **organize and analyze their exam papers** using AI.  
Students can upload exam questions, and the system classifies each question by **strand, topic, and subtopic**, with a confidence measure.

The app helps students:
- Identify **weak areas** and topics to revise
- Track progress across multiple papers
- Share results easily with teachers

---

## Features

- Upload questions for a specific **exam board** and **subject**
- AI ranks **top-k subtopics** for each question
- Confidence derived from the **difference between the top 2 similarity scores**
- All sessions, questions, and predictions stored in **SQLite**
- Retrieve sessions via a **frontend-friendly API**

---

## How It Works

1. **Session Creation** – Each paper gets a unique `session_id`.  
2. **Question Submission** – Questions are stored with number and text.  
3. **AI Classification** – Computes similarity between questions and known subtopics using a **sentence-transformer**.  
4. **Confidence Calculation** – Based on the **margin between top 2 similarity scores**, categorized as `high`, `medium`, or `low`.  
5. **Session Retrieval** – `GET /session/{session_id}` returns questions with predictions and confidence.

---

## Example Response (Short Overview)

The response includes:
- `session_id`, `exam_board`, `subject`, `model_name`, `created_at`
- `questions`: array of question objects
  - Each question has:
    - `question_id`, `question_number`, `question_text`
    - `confidence`: with `method`, `margin`, `status`
    - `note` (optional)
    - `predictions`: array of top-k predictions
      - Each prediction has `rank`, `strand`, `topic`, `subtopic`, `spec_sub_section`, `similarity_score`, `description`

Example (abbreviated):
```JSON
{
  "session_id": "f3a2b4c5",
  "exam_board": "OCR",
  "subject": "H240",
  "model_name": "sentence-transformer-v1",
  "created_at": "2026-01-12T15:32:11Z",
  "questions": [
    {
      "question_id": 101,
      "question_number": "1",
      "question_text": "Differentiate x^2 sin x",
      "confidence": {
        "method": "top1_minus_top2",
        "margin": 0.11,
        "status": "medium"
      },
      "predictions": [
        {
          "rank": 1,
          "strand": "Pure Mathematics",
          "topic": "Differentiation",
          "subtopic": "Product rule",
          "spec_sub_section": "3.2.1",
          "similarity_score": 0.42
        }
      ]
    }
  ]
}
```
---

## Technology Stack

Backend: FastAPI, Python  
Database: SQLite with SQLModel ORM  
AI Model: Sentence-Transformer embeddings  
Frontend: Simple HTML + JavaScript  

---

## Getting Started

1. Clone the repo:  
git clone https://github.com/kdlegum/topic-classifier.git  
cd exam-paper-ai

2. Install dependencies:  
pip install -r requirements.txt

3. Run the FastAPI server:  
uvicorn main:app --reload

4. Access the interface at:  
http://127.0.0.1:8000

---

## Future Improvements

- Add **topic summary endpoints** with weak-area highlights  
- Support **multiple subjects and exam boards** dynamically  
- Add **export options** (CSV/PDF)  
- Improve confidence measurement using **softmax or entropy-based methods**
