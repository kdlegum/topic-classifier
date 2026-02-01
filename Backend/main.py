from fastapi import FastAPI, HTTPException, Query, UploadFile, File, BackgroundTasks, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from typing import List, Optional
import numpy as np
import json
import time
import uuid
import datetime
from Backend.sessionDatabase import Session as DBSess, Question as DBQuestion, Prediction as DBPrediction, QuestionMark
from sqlmodel import Session, create_engine, select, update
from pathlib import Path
from pdf_interpretation.pdfOCR import run_olmocr
from pdf_interpretation.utils import updateStatus
from pdf_interpretation.markdownParser import parse_exam_markdown
from Backend.auth import get_user

engine = create_engine("sqlite:///exam_app.db")
debug = False
limiter = Limiter(key_func=get_remote_address)

app = FastAPI()

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

UPLOAD_DIR = Path(r"Backend\uploads\pdfs")
UPLOAD_DIR.mkdir(exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],     # allowing all origins for now
    allow_methods=["*"],     
    allow_headers=["*"],     
)

@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded"}
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

f = open(r"Backend\topics.json", "r", encoding="utf-8")
allSpecs = json.load(f)


g = open(r"Backend\subtopics_index.json", "r", encoding="utf-8")
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


def encode_text(text: str):
    return model.encode([text]).tolist()

#Need to fix this to require the specification code to get the correct sub_topics_embed
def compute_similarity(req: similarityRequest):
    t0 = time.time()
    embed1 = model.encode(req.questions)
    sub_topics_embed = model.encode(req.SpecDescriptions)
    similarity = model.similarity(sub_topics_embed, embed1)
    print(f"Computed similarity for {len(req.questions)} questions in {time.time() - t0:.2f} seconds")
    return similarity.tolist()


def classify_questions_logic(
    req: classificationRequest,
    *,
    user_id: str,
    is_guest: bool,
):

    matching_topic = None
    for s in allSpecs:
        if s["Specification"] == req.SpecCode:
            matching_topic = s
            break

    if matching_topic is None:
        raise HTTPException(status_code=404, detail="Specification code not found")

    topicList = matching_topic["Topics"]

    subTopicClassificationTexts = []
    for t in topicList:
        topicName = t["Topic_name"]
        for s in t["Sub_topics"]:
            subTopicClassificationTexts.append(
                topicName + ". " + s["description"]
            )

    similarities = np.array(
        compute_similarity(
            similarityRequest(
                questions=req.question_text,
                SpecDescriptions=subTopicClassificationTexts,
            )
        )
    )

    k = req.num_predictions or 3

    topk_indices = np.argsort(similarities, axis=0)[-k:][::-1]
    topk_indices = list(map(list, zip(*topk_indices)))
    topk_indices = [list(map(int, row)) for row in topk_indices]

    session_id = str(uuid.uuid4())

    with Session(engine) as db:

        # Fill ExamBoard if missing
        if req.ExamBoard is None:
            for spec in allSpecs:
                if spec["Specification"] == req.SpecCode:
                    req.ExamBoard = spec["Exam Board"]
                    break
            else:
                req.ExamBoard = "Unknown"

        db_session = DBSess(
            session_id=session_id,
            exam_board=req.ExamBoard,
            subject=req.SpecCode,
            is_guest=is_guest,
            user_id=user_id,
        )
        db.add(db_session)

        for q_idx, question_text in enumerate(req.question_text):

            db_question = DBQuestion(
                session_id=session_id,
                question_number=str(q_idx + 1),
                question_text=question_text,
            )
            db.add(db_question)
            db.flush()  # needed here to get db_question.id

            with open(r"Backend\topics.json", "r", encoding="utf-8") as h:
                topics = json.load(h)

            subTopicIds = []
            for spec in topics:
                if spec["Specification"] == req.SpecCode:
                    for t in spec["Topics"]:
                        for s in t["Sub_topics"]:
                            subTopicIds.append(s["subtopic_id"])

            for rank, subtopic_idx in enumerate(topk_indices[q_idx], start=1):
                subtopic_id = subTopicIds[subtopic_idx]
                key = f"{req.ExamBoard}_{req.SpecCode}_{subtopic_id}"

                if key not in subtopics_index:
                    raise KeyError("Key was not found in subtopics_index")

                info = subtopics_index[key]
                similarity_score = float(
                    round(similarities[subtopic_idx, q_idx], 4)
                )

                db_prediction = DBPrediction(
                    question_id=db_question.id,
                    rank=rank,
                    strand=info["strand"],
                    topic=info["topic_name"],
                    subtopic=info["name"],
                    spec_sub_section=info["spec_sub_section"],
                    description=info["description"],
                    similarity_score=similarity_score,
                )
                db.add(db_prediction)

        db.commit()

    return get_session(session_id)


@app.post("/classify/")
@limiter.limit("5/minute")
def classify_questions(
    request: Request,
    req: classificationRequest,
    user=Depends(get_user),
):
    print(user)

    if user["is_authenticated"]:
        user_id = user["user_id"]
        is_guest = False
    else:
        user_id = user["guest_id"]
        is_guest = True

    return classify_questions_logic(
        req,
        user_id=user_id,
        is_guest=is_guest,
    )



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
@app.get("/upload-pdf-status/{job_id}")
def get_status(job_id: str):
    with open(f"Backend/uploads/status/{job_id}.json", "r") as f:
        data = json.load(f)
    return data

@app.get("/session/{session_id}")
def get_session(session_id: str, request: Request = None, user: dict = None):
    # Allow internal calls (from classify_questions_logic) without auth check
    if request is not None and user is None:
        user = get_user(request)

    with Session(engine) as db:

        # ---------- Fetch session ----------
        db_session = db.exec(
            select(DBSess).where(DBSess.session_id == session_id)
        ).first()

        if not db_session:
            raise HTTPException(status_code=404, detail="Session not found")

        # ---------- Authorization check ----------
        if user is not None:
            is_owner = False
            if db_session.is_guest:
                # Guest session - check guest_id
                is_owner = (user.get("guest_id") == db_session.user_id)
            else:
                # User session - check user_id
                is_owner = (user.get("user_id") == db_session.user_id)

            if not is_owner:
                raise HTTPException(status_code=403, detail="Not authorized to view this session")

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

        # ---------- Look up spec details ----------
        spec_code = db_session.subject
        qualification = None
        subject_name = None
        for spec in allSpecs:
            if spec["Specification"] == spec_code:
                qualification = spec.get("Qualification")
                subject_name = spec.get("Subject")
                break

        # ---------- Final response ----------
        return {
            "session_id": db_session.session_id,
            "exam_board": db_session.exam_board,
            "spec_code": spec_code,
            "qualification": qualification,
            "subject_name": subject_name,
            "subject": db_session.subject,  # kept for backwards compatibility
            "model_name": getattr(db_session, "model_name", None),
            "created_at": db_session.created_at,
            "user_id": db_session.user_id,
            "questions": response_questions
        }


@app.get("/user/sessions")
def get_user_sessions(request: Request, user=Depends(get_user)):
    """
    Returns sessions for authenticated users OR guests (via X-Guest-ID header).
    Includes: session_id, subject, exam_board, created_at, question_count.
    Ordered by most recent first.
    """
    with Session(engine) as db:
        if user["is_authenticated"]:
            # Authenticated user - get their sessions
            sessions = db.exec(
                select(DBSess)
                .where(DBSess.user_id == user["user_id"])
                .where(DBSess.is_guest == False)
                .order_by(DBSess.created_at.desc())
            ).all()
        else:
            # Guest - get sessions by guest_id
            guest_id = user["guest_id"]
            if not guest_id:
                return []
            sessions = db.exec(
                select(DBSess)
                .where(DBSess.user_id == guest_id)
                .where(DBSess.is_guest == True)
                .order_by(DBSess.created_at.desc())
            ).all()

        result = []
        for s in sessions:
            # Count questions for this session
            question_count = len(db.exec(
                select(DBQuestion).where(DBQuestion.session_id == s.session_id)
            ).all())

            # Look up spec details
            spec_code = s.subject
            qualification = None
            subject_name = None
            for spec in allSpecs:
                if spec["Specification"] == spec_code:
                    qualification = spec.get("Qualification")
                    subject_name = spec.get("Subject")
                    break

            result.append({
                "session_id": s.session_id,
                "subject": s.subject,
                "qualification": qualification,
                "subject_name": subject_name,
                "exam_board": s.exam_board,
                "created_at": s.created_at,
                "question_count": question_count,
            })

        return result


@app.post("/migrate-guest-sessions")
def migrate_guest_sessions(request: Request, user=Depends(get_user)):
    """
    Transfers all sessions with matching guest_id to the authenticated user.
    Called after user signs up to migrate their guest sessions.
    """
    if not user["is_authenticated"]:
        raise HTTPException(status_code=401, detail="Must be authenticated to migrate sessions")

    guest_id = user["guest_id"]
    if not guest_id:
        return {"migrated": 0}

    with Session(engine) as db:
        # Find all guest sessions with this guest_id
        guest_sessions = db.exec(
            select(DBSess)
            .where(DBSess.user_id == guest_id)
            .where(DBSess.is_guest == True)
        ).all()

        count = 0
        for session in guest_sessions:
            session.user_id = user["user_id"]
            session.is_guest = False
            db.add(session)
            count += 1

        db.commit()

        return {"migrated": count}


@app.post("/upload-pdf/{SpecCode}")
async def upload_pdf(request: Request, SpecCode: str, file: UploadFile = File(...), background_tasks: BackgroundTasks=None, user=Depends(get_user),):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files allowed")

    print(user)

    job_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{job_id}.pdf"

    #This writes the entire file byte by byte which is kinda fine for small papers
    #To fix later could read in packets
    with open(file_path, "wb") as f:
        f.write(await file.read())

    status = {
        "job_id": job_id,
        "status": "Processing to markdown",
        "session_id": None
    }

    with open (f"Backend/uploads/status/{job_id}.json", "w") as f:
        json.dump(status, f)
    
    background_tasks.add_task(
        process_pdf,
        job_id,
        SpecCode,
        user
    )

    return {
        "job_id": job_id
    }

def process_pdf(job_id, SpecCode, user):
    run_olmocr(f"Backend/uploads/pdfs/{job_id}.pdf", r"Backend\uploads\markdown")
    updateStatus(job_id, "Converted to Markdown. Extracting questions...")
    questions = parse_exam_markdown(f"Backend/uploads/markdown/{job_id}.md")
    updateStatus(job_id, "Questions extracted. Classifying questions by topic...")
    question_text = [q["text"] for q in questions]
    if user["is_authenticated"]:
        user_id = user["user_id"]
        is_guest = False
    else:
        user_id = user["guest_id"]
        is_guest = True
    session_id = classify_questions_logic(classificationRequest(question_text=question_text, SpecCode=SpecCode), user_id=user_id, is_guest=is_guest)["session_id"]
    updateStatus(job_id, "Done", session_id)

@app.get("/debug/sessions")
def debug_sessions():
    with Session(engine) as db:
        sessions = db.exec(
            select(DBSess).order_by(DBSess.created_at.desc()).limit(20)
        ).all()

        return [
            {
                "session_id": s.session_id,
                "user_id": s.user_id,
                "is_guest": s.is_guest,
                "subject": s.subject,
                "created_at": s.created_at,
            }
            for s in sessions
        ]


app.mount("/static", StaticFiles(directory="website"), name="static")

@app.get("/")
def serve_login():
    return FileResponse("website/index.html")

@app.get("/classify")
def serve_classify():
    return FileResponse("website/classify.html")

@app.get("/history")
def serve_history():
    return FileResponse("website/history.html")

@app.get("/session-view/{session_id}")
def serve_session_view(session_id: str):
    return FileResponse("website/session.html")


