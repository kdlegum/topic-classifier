from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from typing import List, Optional
import numpy as np
import json
import time
import uuid
import datetime
from sessionDatabase import Session as DBSess, Question as DBQuestion, Prediction as DBPrediction
from sqlmodel import Session, create_engine, select
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path


engine = create_engine("sqlite:///exam_app.db")
debug = False

app = FastAPI()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],     # allowing all origins for now
    allow_methods=["*"],     
    allow_headers=["*"],     
)


model = SentenceTransformer('all-MiniLM-L6-v2')

class similarityRequest(BaseModel):
    SpecDescriptions: List[str]
    questions: List[str]

class classificationRequest(BaseModel):
    question_text: List[str]
    ExamBoard: Optional[str] = None
    SpecCode: str
    num_predictions: Optional[int] = 3

f = open("topics.json", "r", encoding="utf-8")
allTopics = json.load(f)


h = open("topics.json", "r", encoding="utf-8")
topics = json.load(h)
topicList = []
subTopicIds = []
for spec in topics:
    for t in spec["Topics"]:
        topicList.append(t)
        for s in t["Sub_topics"]:
            subTopicIds.append(s["subtopic_id"])

g = open("subtopics_index.json", "r", encoding="utf-8")
subtopics_index = json.load(g)

id = 0

def compute_confidence(preds: list[DBPrediction]) -> str:
    if len(preds) < 2:
        return "low"
    return confidence_status(round(preds[0].similarity_score - preds[1].similarity_score, 4))

def compute_margin(preds: list[DBPrediction]) -> float:
    if len(preds) < 2:
        return 0.0
    return round(preds[0].similarity_score - preds[1].similarity_score, 4)

def confidence_status(margin: float) -> str:
    if margin >= 0.15:
        return "high"
    if margin >= 0.08:
        return "medium"
    return "low"


@app.get("/encode/")
def encode_text(text: str):
    return model.encode([text]).tolist()

#Need to fix this to require the specification code to get the correct sub_topics_embed
@app.post("/similarity/")
def compute_similarity(req: similarityRequest):
    t0 = time.time()
    embed1 = model.encode(req.questions)
    sub_topics_embed = model.encode(req.SpecDescriptions)
    similarity = model.similarity(sub_topics_embed, embed1)
    print(f"Computed similarity for {len(req.questions)} questions in {time.time() - t0:.2f} seconds")
    return similarity.tolist()



@app.post("/classify/")
def classify_questions(req: classificationRequest):

    """
    Get correct topic list using specficiation code.
    """

    matching_topic = None
    for s in allTopics:
        if s["Specification"] == req.SpecCode:
            matching_topic = s
            break
    
    if matching_topic is None:
        raise HTTPException(status_code=404, detail="Specification code not found")
    
    topics = matching_topic
        
    topicList = topics["Topics"]
    subTopicClassificationTexts = []
    for t in topicList:
        topicName = t["Topic_name"]
        for s in t["Sub_topics"]:
            subTopicClassificationTexts.append(topicName + ". " + s["description"])
    



    """
    Classify a list of questions and store top-k predictions in the DB.
    """
    similarities = np.array(
        compute_similarity(similarityRequest(questions=req.question_text, SpecDescriptions=subTopicClassificationTexts))
    )

    num_questions = similarities.shape[1]
    k = req.num_predictions or 3

  
    topk_indices = np.argsort(similarities, axis=0)[-k:][::-1]

    session_id = str(uuid.uuid4())
    questions = []

    with Session(engine) as db:

        #Identify exam board by SpecCode if not provided

        if req.ExamBoard is None:
            for spec in allTopics:
                if spec["Specification"] == req.SpecCode:
                    req.ExamBoard = spec["Exam Board"]
                    break
                else:
                    req.ExamBoard = "Unknown"

        db_session = DBSess(
            session_id=session_id,
            exam_board=req.ExamBoard,
            subject=req.SpecCode
        )
        db.add(db_session)

        for q_idx, question_text in enumerate(req.question_text):
         
            db_question = DBQuestion(
                session_id=session_id,
                question_number=str(q_idx + 1),
                question_text=question_text
            )
            db.add(db_question)
            db.flush()  # Needed to get db_question.id
 
            question_results = []

            for rank, subtopic_idx in enumerate(topk_indices[:, q_idx], start=1):
                subtopic_id = subTopicIds[subtopic_idx]
                key = f"{req.ExamBoard}_{req.SpecCode}_{subtopic_id}"

                if key not in subtopics_index:
                    continue

                info = subtopics_index[key]
                similarity_score = float(round(similarities[subtopic_idx, q_idx], 4))

                db_prediction = DBPrediction(
                    question_id=db_question.id,
                    rank=rank,
                    strand=info["strand"],
                    topic=info["topic_name"],
                    subtopic=info["name"],
                    spec_sub_section=info["spec_sub_section"],
                    description=info["description"],
                    similarity_score=similarity_score
                )

                db.add(db_prediction)


 

        db.commit()

    return get_session(session_id)



"""
Example response structure:
{
  "session_id": "string",
  "exam_board": "string",
  "subject": "string",
  "model_name": "string",
  "created_at": "datetime",
  "questions": [
    {
      "question_id": "int",
      "question_number": "string",
      "question_text": "string",
      "confidence": {
        "method": "top1_minus_top2",
        "margin": "float",
        "status": "low|medium|high"
      },
      "note": "optional string",
      "predictions": [
        {
          "rank": "int",
          "strand": "string",
          "topic": "string",
          "subtopic": "string",
          "spec_sub_section": "string",
          "similarity_score": "float",
          "description": "optional string"
        }
      ]
    }
  ]
}
"""

@app.get("/session/{session_id}")
def get_session(session_id: str):
    with Session(engine) as db:

        # ---------- Fetch session ----------
        db_session = db.exec(
            select(DBSess).where(DBSess.session_id == session_id)
        ).first()

        if not db_session:
            raise HTTPException(status_code=404, detail="Session not found")

        # ---------- Fetch questions ----------
        questions = db.exec(
            select(DBQuestion)
            .where(DBQuestion.session_id == session_id)
            .order_by(DBQuestion.id)
        ).all()

        question_ids = [q.id for q in questions]

        # ---------- Fetch predictions ----------
        predictions = db.exec(
            select(DBPrediction)
            .where(DBPrediction.question_id.in_(question_ids))
            .order_by(DBPrediction.question_id, DBPrediction.rank)
        ).all()

        # ---------- Group predictions by question ----------
        preds_by_question: dict[int, list[DBPrediction]] = {}
        for p in predictions:
            preds_by_question.setdefault(p.question_id, []).append(p)

        # ---------- Build response ----------
        response_questions = []

        for q in questions:
            preds = preds_by_question.get(q.id, [])

            status = compute_confidence(preds)
            margin = compute_margin(preds)

            note = None

            response_questions.append({
                "question_id": q.id,
                "question_number": q.question_number,
                "question_text": q.question_text,

                "confidence": {
                    "method": "top1_minus_top2",
                    "margin": margin,
                    "status": status
                },

                "note": note,

                "predictions": [
                    {
                        "rank": p.rank,
                        "strand": p.strand,
                        "topic": p.topic,
                        "subtopic": p.subtopic,
                        "spec_sub_section": p.spec_sub_section,
                        "similarity_score": p.similarity_score,
                        "description": p.description
                    }
                    for p in preds
                ]
            })

        # ---------- Final response ----------
        return {
            "session_id": db_session.session_id,
            "exam_board": db_session.exam_board,
            "subject": db_session.subject,
            "model_name": getattr(db_session, "model_name", None),
            "created_at": db_session.created_at,
            "questions": response_questions
        }

@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files allowed")

    job_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{job_id}.pdf"

    #This writes the entire file byte by byte which is kinda fine for small papers
    #To fix later could read in packets
    with open(file_path, "wb") as f:
        f.write(await file.read())

    return {
        "job_id": job_id,
        "filename": file.filename
    }
