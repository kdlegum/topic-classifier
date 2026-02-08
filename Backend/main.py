from fastapi import FastAPI, HTTPException, Query, UploadFile, File, BackgroundTasks, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from typing import List, Optional, Dict
import numpy as np
import json
import time
import uuid
import datetime
from Backend.sessionDatabase import Session as DBSess, Question as DBQuestion, Prediction as DBPrediction, QuestionMark, UserCorrection, Specification, Topic, Subtopic, UserModuleSelection, SessionStrand
from sqlmodel import Session, select, update
from pathlib import Path
import os

try:
    from pdf_interpretation.pdfOCR import run_olmocr
    OLMOCR_AVAILABLE = True
except ImportError:
    OLMOCR_AVAILABLE = False
    run_olmocr = None

from pdf_interpretation.utils import updateStatus
from pdf_interpretation.markdownParser import parse_exam_markdown
from Backend.auth import get_user
from Backend.database import engine
limiter = Limiter(key_func=get_remote_address)

app = FastAPI()

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

UPLOAD_DIR = Path("Backend/uploads/pdfs")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
Path("Backend/uploads/status").mkdir(parents=True, exist_ok=True)
Path("Backend/uploads/markdown").mkdir(parents=True, exist_ok=True)

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
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
    question_object: List[Dict]
    ExamBoard: Optional[str] = None
    SpecCode: str
    num_predictions: Optional[int] = 3
    strands: Optional[List[str]] = None

def load_specs_from_db():
    """
    Query Specification/Topic/Subtopic tables and build the same
    allSpecs list and subtopics_index dict that the JSON files provided.
    Uses 3 bulk queries instead of per-row queries to avoid N+1 latency.
    """
    _allSpecs = []
    _subtopics_index = {}

    with Session(engine) as db:
        specs = db.exec(select(Specification)).all()
        all_topics = db.exec(select(Topic)).all()
        all_subtopics = db.exec(select(Subtopic)).all()

    # Group topics by specification_id
    topics_by_spec: dict[int, list] = {}
    topic_by_id: dict[int, Topic] = {}
    for t in all_topics:
        topics_by_spec.setdefault(t.specification_id, []).append(t)
        topic_by_id[t.id] = t

    # Group subtopics by topic_db_id
    subtopics_by_topic: dict[int, list] = {}
    for s in all_subtopics:
        subtopics_by_topic.setdefault(s.topic_db_id, []).append(s)

    for spec in specs:
        topics_list = []
        for t in topics_by_spec.get(spec.id, []):
            sub_topics_list = []
            for s in subtopics_by_topic.get(t.id, []):
                sub_topics_list.append({
                    "subtopic_id": s.subtopic_id,
                    "Specification_section_sub": s.specification_section_sub,
                    "Sub_topic_name": s.subtopic_name,
                    "description": s.description,
                })

                key = f"{spec.exam_board}_{spec.spec_code}_{s.subtopic_id}"
                _subtopics_index[key] = {
                    "subtopic_id": s.subtopic_id,
                    "name": s.subtopic_name,
                    "description": s.description,
                    "topic_id": t.topic_id_within_spec,
                    "topic_name": t.topic_name,
                    "topic_specification_section": t.specification_section,
                    "strand": t.strand,
                    "qualification": spec.qualification,
                    "subject": spec.subject,
                    "exam_board": spec.exam_board,
                    "specification": spec.spec_code,
                    "spec_sub_section": s.specification_section_sub,
                    "classification_text": f"{s.subtopic_name}. {s.description}",
                }

            topics_list.append({
                "Topic_id": t.topic_id_within_spec,
                "Specification_section": t.specification_section,
                "Strand": t.strand,
                "Topic_name": t.topic_name,
                "Sub_topics": sub_topics_list,
            })

        _allSpecs.append({
            "Qualification": spec.qualification,
            "Subject": spec.subject,
            "Exam Board": spec.exam_board,
            "Specification": spec.spec_code,
            "optional_modules": spec.optional_modules,
            "Topics": topics_list,
        })

    return _allSpecs, _subtopics_index


allSpecs, subtopics_index = load_specs_from_db()

@app.get("/specs")
def get_specs():
    """Returns all specifications with their strands and optional_modules flag."""
    result = []
    for s in allSpecs:
        strands = list({t["Strand"] for t in s["Topics"]})
        result.append({
            "spec_code": s["Specification"],
            "subject": s["Subject"],
            "exam_board": s["Exam Board"],
            "qualification": s["Qualification"],
            "optional_modules": s.get("optional_modules", False),
            "strands": sorted(strands),
        })
    return result


@app.get("/user/modules/{spec_code}")
def get_user_modules(spec_code: str, request: Request, user=Depends(get_user)):
    """Returns the user's saved strand selections for a spec."""
    if user["is_authenticated"]:
        user_id = user["user_id"]
        is_guest = False
    else:
        user_id = user["guest_id"]
        is_guest = True

    with Session(engine) as db:
        rows = db.exec(
            select(UserModuleSelection)
            .where(UserModuleSelection.user_id == user_id)
            .where(UserModuleSelection.is_guest == is_guest)
            .where(UserModuleSelection.spec_code == spec_code)
        ).all()

        return {
            "spec_code": spec_code,
            "selected_strands": [r.strand for r in rows],
        }


class SaveModulesRequest(BaseModel):
    strands: List[str]


@app.put("/user/modules/{spec_code}")
def save_user_modules(spec_code: str, req: SaveModulesRequest, request: Request, user=Depends(get_user)):
    """Full-replacement save of user's strand selections for a spec."""
    # Validate spec exists and has optional_modules
    matching_spec = None
    for s in allSpecs:
        if s["Specification"] == spec_code:
            matching_spec = s
            break
    if matching_spec is None:
        raise HTTPException(status_code=404, detail="Specification not found")

    # Validate strands exist in spec
    valid_strands = {t["Strand"] for t in matching_spec["Topics"]}
    for strand in req.strands:
        if strand not in valid_strands:
            raise HTTPException(status_code=400, detail=f"Invalid strand: {strand}")

    if user["is_authenticated"]:
        user_id = user["user_id"]
        is_guest = False
    else:
        user_id = user["guest_id"]
        is_guest = True

    with Session(engine) as db:
        # Delete existing selections
        existing = db.exec(
            select(UserModuleSelection)
            .where(UserModuleSelection.user_id == user_id)
            .where(UserModuleSelection.is_guest == is_guest)
            .where(UserModuleSelection.spec_code == spec_code)
        ).all()
        for e in existing:
            db.delete(e)

        # Insert new selections
        for strand in req.strands:
            db.add(UserModuleSelection(
                user_id=user_id,
                is_guest=is_guest,
                spec_code=spec_code,
                strand=strand,
            ))

        db.commit()

    return {"success": True}


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

    # Resolve effective strands for filtering
    effective_strands: set[str] | None = None
    if req.strands:
        effective_strands = set(req.strands)
    elif matching_topic.get("optional_modules", False):
        # Look up user's module selections
        with Session(engine) as db:
            rows = db.exec(
                select(UserModuleSelection)
                .where(UserModuleSelection.user_id == user_id)
                .where(UserModuleSelection.is_guest == is_guest)
                .where(UserModuleSelection.spec_code == req.SpecCode)
            ).all()
            if rows:
                effective_strands = {r.strand for r in rows}

    topicList = matching_topic["Topics"]

    # Filter topics by effective strands if set
    if effective_strands:
        topicList = [t for t in topicList if t["Strand"] in effective_strands]
        if not topicList:
            raise HTTPException(status_code=400, detail="No topics match the selected strands")

    subTopicClassificationTexts = []
    subTopicIds = []
    for t in topicList:
        topicName = t["Topic_name"]
        for s in t["Sub_topics"]:
            subTopicClassificationTexts.append(
                topicName + ". " + s["description"]
            )
            subTopicIds.append(s["subtopic_id"])


    question_text = [q["text"] for q in req.question_object]
    marks = [q["marks"] for q in req.question_object]

    similarities = np.array(
        compute_similarity(
            similarityRequest(
                questions=question_text,
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
        db.flush()

        # Store session strands if any were specified
        if effective_strands:
            for strand in effective_strands:
                db.add(SessionStrand(session_id=session_id, strand=strand))

        for q_idx, question_text in enumerate(question_text):

            db_question = DBQuestion(
                session_id=session_id,
                question_number=str(q_idx + 1),
                question_text=question_text,
            )
            db.add(db_question)
            db.flush()  # needed here to get db_question.id

            db_question_mark = QuestionMark(
                question_id=db_question.id,
                marks_available=marks[q_idx],
            )
            db.add(db_question_mark)

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

        # ---------- Fetch question marks ----------
        question_marks = db.exec(
            select(QuestionMark)
            .where(QuestionMark.question_id.in_(question_ids))
        ).all()

        # ---------- Fetch user corrections ----------
        user_corrections = db.exec(
            select(UserCorrection)
            .where(UserCorrection.question_id.in_(question_ids))
        ).all()

        # ---------- Group predictions by question ----------
        preds_by_question: dict[int, list[DBPrediction]] = {}
        for p in predictions:
            preds_by_question.setdefault(p.question_id, []).append(p)

        # ---------- Map marks by question ----------
        marks_by_question: dict[int, QuestionMark] = {}
        for m in question_marks:
            marks_by_question[m.question_id] = m

        # ---------- Group corrections by question ----------
        corrections_by_question: dict[int, list[UserCorrection]] = {}
        for c in user_corrections:
            corrections_by_question.setdefault(c.question_id, []).append(c)

        response_questions = []

        for q in questions:
            preds = preds_by_question.get(q.id, [])
            marks = marks_by_question.get(q.id)

            status = compute_confidence(preds)
            margin = compute_margin(preds)

            note = None

            response_questions.append({
                "question_id": q.id,
                "question_number": q.question_number,
                "question_text": q.question_text,
                "marks_available": marks.marks_available if marks else None,
                "marks_achieved": marks.marks_achieved if marks else None,

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
                ],

                "user_corrections": [
                    {
                        "subtopic_id": c.subtopic_id,
                        "strand": c.strand,
                        "topic": c.topic,
                        "subtopic": c.subtopic,
                        "spec_sub_section": c.spec_sub_section,
                        "description": c.description
                    }
                    for c in corrections_by_question.get(q.id, [])
                ]
            })

        # ---------- Fetch session strands ----------
        session_strands_rows = db.exec(
            select(SessionStrand).where(SessionStrand.session_id == session_id)
        ).all()
        session_strands = [r.strand for r in session_strands_rows]

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
            "session_strands": session_strands,
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
            sessions = db.exec(
                select(DBSess)
                .where(DBSess.user_id == user["user_id"])
                .where(DBSess.is_guest == False)
                .order_by(DBSess.created_at.desc())
            ).all()
        else:
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

        # Migrate UserModuleSelection rows
        guest_modules = db.exec(
            select(UserModuleSelection)
            .where(UserModuleSelection.user_id == guest_id)
            .where(UserModuleSelection.is_guest == True)
        ).all()
        for mod in guest_modules:
            mod.user_id = user["user_id"]
            mod.is_guest = False
            db.add(mod)

        db.commit()

        return {"migrated": count}


@app.post("/upload-pdf/{SpecCode}")
async def upload_pdf(
    request: Request,
    SpecCode: str,
    file: UploadFile = File(...),
    strands: Optional[str] = Query(default=None, description="Comma-separated strand names"),
    background_tasks: BackgroundTasks = None,
    user=Depends(get_user),
):
    if not OLMOCR_AVAILABLE:
        raise HTTPException(status_code=503, detail="PDF processing is not available on this server")
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files allowed")

    print(user)

    strand_list = [s.strip() for s in strands.split(",")] if strands else None

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
        user,
        strand_list
    )

    return {
        "job_id": job_id
    }

def process_pdf(job_id, SpecCode, user, strands=None):
    run_olmocr(f"Backend/uploads/pdfs/{job_id}.pdf", "Backend/uploads/markdown")
    updateStatus(job_id, "Converted to Markdown. Extracting questions...")
    questions = parse_exam_markdown(f"Backend/uploads/markdown/{job_id}.md")
    updateStatus(job_id, "Questions extracted. Classifying questions by topic...")

    if user["is_authenticated"]:
        user_id = user["user_id"]
        is_guest = False
    else:
        user_id = user["guest_id"]
        is_guest = True

    session_id = classify_questions_logic(classificationRequest(question_object=questions, SpecCode=SpecCode, strands=strands), user_id=user_id, is_guest=is_guest)["session_id"]
    updateStatus(job_id, "Done", session_id)

class UpdateQuestionRequest(BaseModel):
    question_text: Optional[str] = None
    marks_available: Optional[int] = None

@app.patch("/session/{session_id}/question/{question_id}")
def update_question(session_id: str, question_id: int, req: UpdateQuestionRequest, request: Request, user=Depends(get_user)):
    with Session(engine) as db:
        db_session = db.exec(
            select(DBSess).where(DBSess.session_id == session_id)
        ).first()
        if not db_session:
            raise HTTPException(status_code=404, detail="Session not found")

        is_owner = False
        if db_session.is_guest:
            is_owner = (user.get("guest_id") == db_session.user_id)
        else:
            is_owner = (user.get("user_id") == db_session.user_id)
        if not is_owner:
            raise HTTPException(status_code=403, detail="Not authorized to modify this session")

        question = db.exec(
            select(DBQuestion).where(DBQuestion.id == question_id, DBQuestion.session_id == session_id)
        ).first()
        if not question:
            raise HTTPException(status_code=404, detail="Question not found in this session")

        if req.question_text is not None:
            question.question_text = req.question_text
            db.add(question)

        if req.marks_available is not None:
            question_mark = db.exec(
                select(QuestionMark).where(QuestionMark.question_id == question_id)
            ).first()
            if question_mark:
                question_mark.marks_available = req.marks_available
                db.add(question_mark)

            # Recalculate session total_marks_available
            all_question_ids = [q.id for q in db.exec(
                select(DBQuestion).where(DBQuestion.session_id == session_id)
            ).all()]
            all_marks = db.exec(
                select(QuestionMark).where(QuestionMark.question_id.in_(all_question_ids))
            ).all()
            db_session.total_marks_available = sum(m.marks_available or 0 for m in all_marks)
            db.add(db_session)

        db.commit()

        return {
            "question_id": question_id,
            "question_text": question.question_text,
            "marks_available": req.marks_available,
        }

class MarkSubmission(BaseModel):
    question_id: int
    marks_achieved: int

class MarksSubmitRequest(BaseModel):
    marks: List[MarkSubmission]

@app.post("/session/{session_id}/marks")
def submit_marks(session_id: str, req: MarksSubmitRequest, request: Request, user=Depends(get_user)):
    """
    Submit achieved marks for questions in a session.
    Updates QuestionMark records and recalculates session totals.
    """
    with Session(engine) as db:
        # Fetch session and verify ownership
        db_session = db.exec(
            select(DBSess).where(DBSess.session_id == session_id)
        ).first()

        if not db_session:
            raise HTTPException(status_code=404, detail="Session not found")

        is_owner = False
        if db_session.is_guest:
            is_owner = (user.get("guest_id") == db_session.user_id)
        else:
            is_owner = (user.get("user_id") == db_session.user_id)

        if not is_owner:
            raise HTTPException(status_code=403, detail="Not authorized to modify this session")

        questions = db.exec(
            select(DBQuestion).where(DBQuestion.session_id == session_id)
        ).all()
        valid_question_ids = {q.id for q in questions}

        for mark in req.marks:
            if mark.question_id not in valid_question_ids:
                raise HTTPException(
                    status_code=400,
                    detail=f"Question {mark.question_id} does not belong to this session"
                )

            question_mark = db.exec(
                select(QuestionMark).where(QuestionMark.question_id == mark.question_id)
            ).first()

            if not question_mark:
                raise HTTPException(
                    status_code=404,
                    detail=f"QuestionMark not found for question {mark.question_id}"
                )

            question_mark.marks_achieved = mark.marks_achieved
            db.add(question_mark)

            # Update question status to marked
            question = db.exec(
                select(DBQuestion).where(DBQuestion.id == mark.question_id)
            ).first()
            if question:
                question.status = "marked"
                db.add(question)

        # Recalculate session totals
        all_marks = db.exec(
            select(QuestionMark).where(
                QuestionMark.question_id.in_(valid_question_ids)
            )
        ).all()

        total_available = sum(m.marks_available or 0 for m in all_marks)
        total_achieved = sum(m.marks_achieved or 0 for m in all_marks if m.marks_achieved is not None)
        all_marked = all(m.marks_achieved is not None for m in all_marks)

        db_session.total_marks_available = total_available
        db_session.total_marks_achieved = total_achieved
        db_session.status = "marked" if all_marked else "in_progress"
        db.add(db_session)

        db.commit()

        return {
            "success": True,
            "total_marks_available": total_available,
            "total_marks_achieved": total_achieved,
            "session_status": db_session.status
        }


@app.get("/topics/{spec_code}/hierarchy")
def get_topic_hierarchy(spec_code: str):
    matching_spec = None
    for s in allSpecs:
        if s["Specification"] == spec_code:
            matching_spec = s
            break

    if matching_spec is None:
        raise HTTPException(status_code=404, detail="Specification not found")

    exam_board = matching_spec["Exam Board"]
    strands: dict[str, dict] = {}

    for t in matching_spec["Topics"]:
        strand_name = t["Strand"]
        if strand_name not in strands:
            strands[strand_name] = {"name": strand_name, "topics": []}

        subtopics = []
        for s in t["Sub_topics"]:
            subtopics.append({
                "subtopic_id": s["subtopic_id"],
                "name": s["Sub_topic_name"],
                "spec_sub_section": s["Specification_section_sub"],
                "description": s["description"],
            })

        strands[strand_name]["topics"].append({
            "topic_id": t["Topic_id"],
            "name": t["Topic_name"],
            "subtopics": subtopics,
        })

    return {
        "spec_code": spec_code,
        "exam_board": exam_board,
        "strands": list(strands.values()),
    }


class CorrectionItem(BaseModel):
    question_id: int
    subtopic_ids: List[str]

class CorrectionsRequest(BaseModel):
    corrections: List[CorrectionItem]

@app.put("/session/{session_id}/corrections")
def save_corrections(session_id: str, req: CorrectionsRequest, request: Request, user=Depends(get_user)):
    with Session(engine) as db:
        db_session = db.exec(
            select(DBSess).where(DBSess.session_id == session_id)
        ).first()

        if not db_session:
            raise HTTPException(status_code=404, detail="Session not found")

        is_owner = False
        if db_session.is_guest:
            is_owner = (user.get("guest_id") == db_session.user_id)
        else:
            is_owner = (user.get("user_id") == db_session.user_id)
        if not is_owner:
            raise HTTPException(status_code=403, detail="Not authorized to modify this session")

        valid_question_ids = {q.id for q in db.exec(
            select(DBQuestion).where(DBQuestion.session_id == session_id)
        ).all()}

        exam_board = db_session.exam_board
        spec_code = db_session.subject

        for item in req.corrections:
            if item.question_id not in valid_question_ids:
                raise HTTPException(status_code=400, detail=f"Question {item.question_id} does not belong to this session")

            # Delete existing corrections for this question
            existing = db.exec(
                select(UserCorrection).where(UserCorrection.question_id == item.question_id)
            ).all()
            for e in existing:
                db.delete(e)

            # Insert new corrections
            for subtopic_id in item.subtopic_ids:
                key = f"{exam_board}_{spec_code}_{subtopic_id}"
                if key not in subtopics_index:
                    raise HTTPException(status_code=400, detail=f"Invalid subtopic_id: {subtopic_id}")

                info = subtopics_index[key]
                correction = UserCorrection(
                    question_id=item.question_id,
                    subtopic_id=subtopic_id,
                    exam_board=exam_board,
                    spec_code=spec_code,
                    strand=info["strand"],
                    topic=info["topic_name"],
                    subtopic=info["name"],
                    spec_sub_section=info["spec_sub_section"],
                    description=info["description"],
                )
                db.add(correction)

        db.commit()

    return {"success": True}


@app.get("/analytics/summary")
def get_analytics_summary(request: Request, user=Depends(get_user)):
    """
    Returns aggregated analytics data for the current user:
    - sessions_over_time: per-session score summaries
    - strand_performance: per-session strand marks (keyed by session_id)
    - topic_performance: per-session topic marks (keyed by session_id)
    """
    with Session(engine) as db:
        # Fetch user sessions
        if user["is_authenticated"]:
            sessions = db.exec(
                select(DBSess)
                .where(DBSess.user_id == user["user_id"])
                .where(DBSess.is_guest == False)
                .order_by(DBSess.created_at.asc())
            ).all()
        else:
            guest_id = user["guest_id"]
            if not guest_id:
                return {"sessions_over_time": [], "strand_performance": []}
            sessions = db.exec(
                select(DBSess)
                .where(DBSess.user_id == guest_id)
                .where(DBSess.is_guest == True)
                .order_by(DBSess.created_at.asc())
            ).all()

        if not sessions:
            return {"sessions_over_time": [], "strand_performance": []}

        session_ids = [s.session_id for s in sessions]

        # Fetch all questions for these sessions
        questions = db.exec(
            select(DBQuestion).where(DBQuestion.session_id.in_(session_ids))
        ).all()

        question_ids = [q.id for q in questions]
        questions_by_session: dict[str, list] = {}
        for q in questions:
            questions_by_session.setdefault(q.session_id, []).append(q)

        if not question_ids:
            return {"sessions_over_time": [], "strand_performance": []}

        # Fetch marks, rank-1 predictions, and user corrections
        marks = db.exec(
            select(QuestionMark).where(QuestionMark.question_id.in_(question_ids))
        ).all()
        marks_by_q: dict[int, QuestionMark] = {m.question_id: m for m in marks}

        rank1_preds = db.exec(
            select(DBPrediction)
            .where(DBPrediction.question_id.in_(question_ids))
            .where(DBPrediction.rank == 1)
        ).all()
        preds_by_q: dict[int, DBPrediction] = {p.question_id: p for p in rank1_preds}

        corrections = db.exec(
            select(UserCorrection).where(UserCorrection.question_id.in_(question_ids))
        ).all()
        corrections_by_q: dict[int, list[UserCorrection]] = {}
        for c in corrections:
            corrections_by_q.setdefault(c.question_id, []).append(c)

        # Build sessions_over_time
        sessions_over_time = []
        for s in sessions:
            s_questions = questions_by_session.get(s.session_id, [])
            question_count = len(s_questions)

            total_available = 0
            total_achieved = 0
            has_any_marks = False

            for q in s_questions:
                m = marks_by_q.get(q.id)
                if m:
                    total_available += m.marks_available or 0
                    if m.marks_achieved is not None:
                        total_achieved += m.marks_achieved
                        has_any_marks = True

            # Look up spec details
            subject_name = None
            for spec in allSpecs:
                if spec["Specification"] == s.subject:
                    subject_name = spec.get("Subject")
                    break

            percentage = None
            if has_any_marks and total_available > 0:
                percentage = round((total_achieved / total_available) * 100, 1)

            sessions_over_time.append({
                "session_id": s.session_id,
                "spec_code": s.subject,
                "subject_name": subject_name,
                "exam_board": s.exam_board,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "question_count": question_count,
                "total_available": total_available,
                "total_achieved": total_achieved if has_any_marks else None,
                "percentage": percentage,
            })

        # Build strand_performance and topic_performance (per-session granularity)
        # Use UserCorrection if available, else rank-1 prediction
        strand_agg: dict[tuple[str, str, str], dict] = {}  # (session_id, spec_code, strand)
        topic_agg: dict[tuple[str, str, str], dict] = {}   # (session_id, spec_code, topic)

        # Map question -> session for quick lookup
        session_by_id: dict[str, DBSess] = {s.session_id: s for s in sessions}

        for q in questions:
            m = marks_by_q.get(q.id)
            if not m or m.marks_achieved is None:
                continue

            session_for_q = session_by_id.get(q.session_id)
            spec_code = session_for_q.subject if session_for_q else "Unknown"
            sid = q.session_id

            # Get strands and topics: prefer user corrections, fallback to rank-1 prediction
            q_corrections = corrections_by_q.get(q.id, [])
            if q_corrections:
                strands_for_q = [c.strand for c in q_corrections]
                topics_for_q = [c.topic for c in q_corrections]
            else:
                pred = preds_by_q.get(q.id)
                strands_for_q = [pred.strand] if pred else []
                topics_for_q = [pred.topic] if pred else []

            # Split marks evenly if multiple entries (from multiple corrections)
            num_entries = len(strands_for_q)
            if num_entries == 0:
                continue

            marks_available_share = (m.marks_available or 0) / num_entries
            marks_achieved_share = (m.marks_achieved or 0) / num_entries

            for strand in strands_for_q:
                key = (sid, spec_code, strand)
                if key not in strand_agg:
                    strand_agg[key] = {
                        "session_id": sid,
                        "spec_code": spec_code,
                        "strand": strand,
                        "marks_available": 0,
                        "marks_achieved": 0,
                        "question_count": 0,
                    }
                strand_agg[key]["marks_available"] += marks_available_share
                strand_agg[key]["marks_achieved"] += marks_achieved_share
                strand_agg[key]["question_count"] += 1

            for i, topic in enumerate(topics_for_q):
                strand = strands_for_q[i] if i < len(strands_for_q) else ""
                key = (sid, spec_code, topic)
                if key not in topic_agg:
                    topic_agg[key] = {
                        "session_id": sid,
                        "spec_code": spec_code,
                        "strand": strand,
                        "topic": topic,
                        "marks_available": 0,
                        "marks_achieved": 0,
                        "question_count": 0,
                    }
                topic_agg[key]["marks_available"] += marks_available_share
                topic_agg[key]["marks_achieved"] += marks_achieved_share
                topic_agg[key]["question_count"] += 1

        strand_performance = []
        for v in strand_agg.values():
            strand_performance.append({
                "session_id": v["session_id"],
                "spec_code": v["spec_code"],
                "strand": v["strand"],
                "marks_available": round(v["marks_available"], 1),
                "marks_achieved": round(v["marks_achieved"], 1),
                "question_count": v["question_count"],
            })

        topic_performance = []
        for v in topic_agg.values():
            topic_performance.append({
                "session_id": v["session_id"],
                "spec_code": v["spec_code"],
                "strand": v["strand"],
                "topic": v["topic"],
                "marks_available": round(v["marks_available"], 1),
                "marks_achieved": round(v["marks_achieved"], 1),
                "question_count": v["question_count"],
            })

        # Count distinct strands per spec from the specification data. A bit scuffed to be honest - but this is for distinguishing for the topic performance widget.
        spec_codes = list({s.subject for s in sessions})
        strands_per_spec: dict[str, int] = {}
        for sc in spec_codes:
            spec_row = db.exec(
                select(Specification).where(Specification.spec_code == sc)
            ).first()
            if spec_row:
                count = len(set(
                    t.strand for t in db.exec(
                        select(Topic).where(Topic.specification_id == spec_row.id)
                    ).all()
                ))
                strands_per_spec[sc] = count

        # Build user_module_selections for optional_modules specs
        user_module_selections: dict[str, list[str]] = {}
        if user["is_authenticated"]:
            uid = user["user_id"]
            is_g = False
        else:
            uid = user["guest_id"]
            is_g = True

        for sc in spec_codes:
            spec_info = next((s for s in allSpecs if s["Specification"] == sc), None)
            if spec_info and spec_info.get("optional_modules", False):
                mod_rows = db.exec(
                    select(UserModuleSelection)
                    .where(UserModuleSelection.user_id == uid)
                    .where(UserModuleSelection.is_guest == is_g)
                    .where(UserModuleSelection.spec_code == sc)
                ).all()
                if mod_rows:
                    user_module_selections[sc] = [r.strand for r in mod_rows]

        return {
            "sessions_over_time": sessions_over_time,
            "strand_performance": strand_performance,
            "topic_performance": topic_performance,
            "strands_per_spec": strands_per_spec,
            "user_module_selections": user_module_selections,
        }


@app.get("/progress/{spec_code}")
def get_progress(spec_code: str, request: Request, user=Depends(get_user)):
    # Validate spec_code
    matching_spec = None
    for s in allSpecs:
        if s["Specification"] == spec_code:
            matching_spec = s
            break
    if matching_spec is None:
        raise HTTPException(status_code=404, detail="Specification not found")

    # For optional_modules specs, filter to user's selected strands
    selected_strands: set[str] | None = None
    if matching_spec.get("optional_modules", False):
        if user["is_authenticated"]:
            uid = user["user_id"]
            is_g = False
        else:
            uid = user["guest_id"]
            is_g = True
        with Session(engine) as db:
            mod_rows = db.exec(
                select(UserModuleSelection)
                .where(UserModuleSelection.user_id == uid)
                .where(UserModuleSelection.is_guest == is_g)
                .where(UserModuleSelection.spec_code == spec_code)
            ).all()
            if mod_rows:
                selected_strands = {r.strand for r in mod_rows}

    # Build subtopic catalog keyed by spec_sub_section
    all_subtopics: dict[str, dict] = {}
    for t in matching_spec["Topics"]:
        if selected_strands and t["Strand"] not in selected_strands:
            continue
        for s in t["Sub_topics"]:
            all_subtopics[s["Specification_section_sub"]] = {
                "subtopic_id": s["subtopic_id"],
                "spec_sub_section": s["Specification_section_sub"],
                "subtopic_name": s["Sub_topic_name"],
                "strand": t["Strand"],
                "topic": t["Topic_name"],
            }

    def build_progress_response(subtopic_stats: dict) -> dict:
        subtopics_list = []
        for spec_sub_section, info in all_subtopics.items():
            stats = subtopic_stats.get(spec_sub_section)
            if stats is None:
                status = "not_revised"
                full_marks_count = 0
                question_count = 0
            else:
                question_count = stats["question_count"]
                full_marks_count = stats["full_marks_count"]
                if full_marks_count >= 3:
                    status = "mastered"
                elif full_marks_count >= 1:
                    status = "secure"
                else:
                    status = "insecure"
            subtopics_list.append({
                **info,
                "status": status,
                "full_marks_count": full_marks_count,
                "question_count": question_count,
            })
        return {"spec_code": spec_code, "subtopics": subtopics_list}

    with Session(engine) as db:
        # Fetch user sessions for this spec
        if user["is_authenticated"]:
            sessions = db.exec(
                select(DBSess)
                .where(DBSess.user_id == user["user_id"])
                .where(DBSess.is_guest == False)
                .where(DBSess.subject == spec_code)
            ).all()
        else:
            guest_id = user["guest_id"]
            if not guest_id:
                return build_progress_response({})
            sessions = db.exec(
                select(DBSess)
                .where(DBSess.user_id == guest_id)
                .where(DBSess.is_guest == True)
                .where(DBSess.subject == spec_code)
            ).all()

        if not sessions:
            return build_progress_response({})

        session_ids = [s.session_id for s in sessions]

        questions = db.exec(
            select(DBQuestion).where(DBQuestion.session_id.in_(session_ids))
        ).all()
        if not questions:
            return build_progress_response({})

        question_ids = [q.id for q in questions]

        # Batch fetch marks, rank-1 predictions, and corrections
        marks = db.exec(
            select(QuestionMark).where(QuestionMark.question_id.in_(question_ids))
        ).all()
        marks_by_q: dict[int, QuestionMark] = {m.question_id: m for m in marks}

        rank1_preds = db.exec(
            select(DBPrediction)
            .where(DBPrediction.question_id.in_(question_ids))
            .where(DBPrediction.rank == 1)
        ).all()
        preds_by_q: dict[int, DBPrediction] = {p.question_id: p for p in rank1_preds}

        corrections = db.exec(
            select(UserCorrection).where(UserCorrection.question_id.in_(question_ids))
        ).all()
        corrections_by_q: dict[int, list[UserCorrection]] = {}
        for c in corrections:
            corrections_by_q.setdefault(c.question_id, []).append(c)

        # Aggregate per subtopic
        subtopic_stats: dict[str, dict] = {}

        for q in questions:
            m = marks_by_q.get(q.id)
            if not m or m.marks_achieved is None:
                continue

            is_full_marks = m.marks_achieved == m.marks_available

            # Use corrections if available, else rank-1 prediction
            q_corrections = corrections_by_q.get(q.id, [])
            if q_corrections:
                spec_sub_sections = [c.spec_sub_section for c in q_corrections]
            else:
                pred = preds_by_q.get(q.id)
                spec_sub_sections = [pred.spec_sub_section] if pred else []

            for sss in spec_sub_sections:
                if sss not in subtopic_stats:
                    subtopic_stats[sss] = {"question_count": 0, "full_marks_count": 0}
                subtopic_stats[sss]["question_count"] += 1
                if is_full_marks:
                    subtopic_stats[sss]["full_marks_count"] += 1

        return build_progress_response(subtopic_stats)


@app.delete("/session/{session_id}")
def delete_session(session_id: str, request: Request, user=Depends(get_user)):
    with Session(engine) as db:
        db_session = db.exec(
            select(DBSess).where(DBSess.session_id == session_id)
        ).first()

        if not db_session:
            raise HTTPException(status_code=404, detail="Session not found")

        is_owner = False
        if db_session.is_guest:
            is_owner = (user.get("guest_id") == db_session.user_id)
        else:
            is_owner = (user.get("user_id") == db_session.user_id)
        if not is_owner:
            raise HTTPException(status_code=403, detail="Not authorized to delete this session")

        question_ids = [q.id for q in db.exec(
            select(DBQuestion).where(DBQuestion.session_id == session_id)
        ).all()]

        if question_ids:
            # Delete predictions, predictions, corrections, questions, and corrections 
            for p in db.exec(select(DBPrediction).where(DBPrediction.question_id.in_(question_ids))).all():
                db.delete(p)
            for m in db.exec(select(QuestionMark).where(QuestionMark.question_id.in_(question_ids))).all():
                db.delete(m)
            for c in db.exec(select(UserCorrection).where(UserCorrection.question_id.in_(question_ids))).all():
                db.delete(c)
            for q in db.exec(select(DBQuestion).where(DBQuestion.session_id == session_id)).all():
                db.delete(q)

        # Delete session strands
        for ss in db.exec(select(SessionStrand).where(SessionStrand.session_id == session_id)).all():
            db.delete(ss)

        # Flush dependent deletes before removing the session itself
        db.flush()

        db.delete(db_session)
        db.commit()

    return {"detail": "Session deleted"}


