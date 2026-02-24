from fastapi import FastAPI, Header, HTTPException, Query, UploadFile, File, BackgroundTasks, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from typing import List, Optional, Dict
import numpy as np
import json
import shutil
import time
import uuid
import datetime
import requests
from Backend.sessionDatabase import Session as DBSess, Question as DBQuestion, Prediction as DBPrediction, QuestionMark, UserCorrection, Specification, Topic, Subtopic, UserModuleSelection, SessionStrand, UserSpecSelection, QuestionLocation, RevisionAttempt, UserTierSelection, PastPaper
from sqlmodel import Session, select, update
from sqlalchemy import func
from pathlib import Path
import os

from pdf_interpretation.pdfOCR import extract_text_pymupdf
from pdf_interpretation.llmParser import parse_pdf_with_vision

try:
    from pdf_interpretation.pdfOCR import run_olmocr
    OLMOCR_AVAILABLE = True
except ImportError:
    OLMOCR_AVAILABLE = False
    run_olmocr = None

from pdf_interpretation.utils import updateStatus
from pdf_interpretation.markdownParser import parse_exam_markdown, merge_questions, sort_questions
from pdf_interpretation.questionLocator import locate_questions_in_pdf
from Backend.auth import get_user
from Backend.database import engine
from Backend.embedding_cache import rebuild as rebuild_embedding_cache, get_embeddings
from paper_scraper.downloader import download_pdf as scraper_download_pdf
from paper_scraper import aqa_config as aqa_scraper_config
from paper_scraper import edexcel_config as edexcel_scraper_config
from paper_scraper import ocr_config as ocr_scraper_config
from paper_scraper.aqa_scraper import fetch_all_results as aqa_fetch_all_results, build_entry as aqa_build_entry
from paper_scraper.edexcel_scraper import fetch_all_hits as edexcel_fetch_all_hits, parse_hit as edexcel_parse_hit
from paper_scraper.ocr_scraper import fetch_resources_html as ocr_fetch_resources_html, parse_resources_html as ocr_parse_resources_html, build_entry as ocr_build_entry
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
    SpecCode: Optional[str] = None
    num_predictions: Optional[int] = 3
    strands: Optional[List[str]] = None
    tier: Optional[str] = None

def load_specs_from_db():
    """
    Query Specification/Topic/Subtopic tables and build the same
    allSpecs dict (keyed by spec_code) and subtopics_index dict that the JSON files provided.
    Uses 3 bulk queries instead of per-row queries to avoid N+1 latency.
    """
    _allSpecs = {}
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

    for spec in [s for s in specs if not s.is_hidden]:
        topics_list = []
        for t in topics_by_spec.get(spec.id, []):
            sub_topics_list = []
            for s in subtopics_by_topic.get(t.id, []):
                sub_topics_list.append({
                    "subtopic_id": s.subtopic_id,
                    "Specification_section_sub": s.specification_section_sub,
                    "Sub_topic_name": s.subtopic_name,
                    "description": s.description,
                    "tier": s.tier,
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
                    "tier": s.tier,
                }

            topics_list.append({
                "Topic_id": t.topic_id_within_spec,
                "Specification_section": t.specification_section,
                "Strand": t.strand,
                "Topic_name": t.topic_name,
                "Sub_topics": sub_topics_list,
            })

        _allSpecs[spec.spec_code] = {
            "Qualification": spec.qualification,
            "Subject": spec.subject,
            "Exam Board": spec.exam_board,
            "Specification": spec.spec_code,
            "optional_modules": spec.optional_modules,
            "has_math": spec.has_math,
            "creator_id": spec.creator_id,
            "creator_is_guest": spec.creator_is_guest,
            "is_reviewed": spec.is_reviewed,
            "description": spec.description,
            "created_at": spec.created_at.isoformat() if spec.created_at else None,
            "Topics": topics_list,
        }

    return _allSpecs, _subtopics_index


allSpecs, subtopics_index = load_specs_from_db()
rebuild_embedding_cache(allSpecs, model)


def reload_specs():
    global allSpecs, subtopics_index
    allSpecs, subtopics_index = load_specs_from_db()
    rebuild_embedding_cache(allSpecs, model)

@app.get("/specs")
def get_specs(request: Request, user=Depends(get_user)):
    """Returns all specifications with their strands, optional_modules flag, and user selection status."""
    if user["is_authenticated"]:
        user_id = user["user_id"]
        is_guest = False
    else:
        user_id = user["guest_id"]
        is_guest = True

    with Session(engine) as db:
        selections = db.exec(
            select(UserSpecSelection)
            .where(UserSpecSelection.user_id == user_id)
            .where(UserSpecSelection.is_guest == is_guest)
        ).all()
    selected_codes = {sel.spec_code for sel in selections}

    result = []
    for code, s in allSpecs.items():
        strands = list({t["Strand"] for t in s["Topics"]})
        topic_count = sum(len(t["Sub_topics"]) for t in s["Topics"])
        tier_values = {sub.get("tier") for t in s["Topics"] for sub in t["Sub_topics"] if sub.get("tier")}
        result.append({
            "spec_code": code,
            "subject": s["Subject"],
            "exam_board": s["Exam Board"],
            "qualification": s["Qualification"],
            "optional_modules": s.get("optional_modules", False),
            "has_math": s.get("has_math", False),
            "strands": sorted(strands),
            "tiers": sorted(tier_values),
            "has_tiers": len(tier_values) > 0,
            "is_reviewed": s.get("is_reviewed", False),
            "creator_id": s.get("creator_id"),
            "description": s.get("description"),
            "created_at": s.get("created_at"),
            "topic_count": topic_count,
            "is_selected": code in selected_codes,
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
    matching_spec = allSpecs.get(spec_code)
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


@app.get("/user/tier/{spec_code}")
def get_user_tier(spec_code: str, request: Request, user=Depends(get_user)):
    """Returns the user's saved tier selection for a spec."""
    if user["is_authenticated"]:
        user_id = user["user_id"]
        is_guest = False
    else:
        user_id = user["guest_id"]
        is_guest = True

    with Session(engine) as db:
        row = db.exec(
            select(UserTierSelection)
            .where(UserTierSelection.user_id == user_id)
            .where(UserTierSelection.is_guest == is_guest)
            .where(UserTierSelection.spec_code == spec_code)
        ).first()

    return {"tier": row.tier if row else None}


class SaveTierRequest(BaseModel):
    tier: Optional[str] = None


@app.put("/user/tier/{spec_code}")
def save_user_tier(spec_code: str, req: SaveTierRequest, request: Request, user=Depends(get_user)):
    """Save or clear the user's tier selection for a spec."""
    if spec_code not in allSpecs:
        raise HTTPException(status_code=404, detail="Specification not found")

    if req.tier is not None and req.tier not in ("Higher", "Foundation"):
        raise HTTPException(status_code=400, detail="tier must be 'Higher', 'Foundation', or null")

    if user["is_authenticated"]:
        user_id = user["user_id"]
        is_guest = False
    else:
        user_id = user["guest_id"]
        is_guest = True

    with Session(engine) as db:
        existing = db.exec(
            select(UserTierSelection)
            .where(UserTierSelection.user_id == user_id)
            .where(UserTierSelection.is_guest == is_guest)
            .where(UserTierSelection.spec_code == spec_code)
        ).first()

        if req.tier is None:
            # Clear the selection
            if existing:
                db.delete(existing)
        else:
            if existing:
                existing.tier = req.tier
                db.add(existing)
            else:
                db.add(UserTierSelection(
                    user_id=user_id,
                    is_guest=is_guest,
                    spec_code=spec_code,
                    tier=req.tier,
                ))

        db.commit()

    return {"success": True}


# ── Custom Spec Creation ──────────────────────────────────────────

class SubtopicCreate(BaseModel):
    subtopic_name: str
    description: str

class TopicCreate(BaseModel):
    strand: str
    topic_name: str
    subtopics: List[SubtopicCreate]

class SpecCreate(BaseModel):
    qualification: str
    subject: str
    exam_board: str
    spec_code: str
    optional_modules: bool = False
    has_math: bool = False
    description: Optional[str] = None
    topics: List[TopicCreate]


@app.post("/specs")
def create_spec(req: SpecCreate, request: Request, user=Depends(get_user)):
    """Create a new custom specification."""
    if user["is_authenticated"]:
        user_id = user["user_id"]
        is_guest = False
    else:
        user_id = user["guest_id"]
        is_guest = True

    # Validate spec_code uniqueness
    if req.spec_code in allSpecs:
        raise HTTPException(status_code=409, detail="Specification code already exists")

    if len(req.topics) < 1:
        raise HTTPException(status_code=400, detail="At least one topic is required")
    for t in req.topics:
        if len(t.subtopics) < 1:
            raise HTTPException(status_code=400, detail=f"Topic '{t.topic_name}' must have at least one subtopic")

    with Session(engine) as db:
        db_spec = Specification(
            qualification=req.qualification,
            subject=req.subject,
            exam_board=req.exam_board,
            spec_code=req.spec_code,
            optional_modules=req.optional_modules,
            has_math=req.has_math,
            description=req.description,
            creator_id=user_id,
            creator_is_guest=is_guest,
            is_reviewed=False,
        )
        db.add(db_spec)
        db.flush()

        for t_idx, topic_data in enumerate(req.topics, start=1):
            db_topic = Topic(
                specification_id=db_spec.id,
                topic_id_within_spec=t_idx,
                specification_section=str(t_idx),
                strand=topic_data.strand,
                topic_name=topic_data.topic_name,
            )
            db.add(db_topic)
            db.flush()

            for s_idx, sub_data in enumerate(topic_data.subtopics):
                letter = chr(ord('a') + s_idx)
                db_subtopic = Subtopic(
                    topic_db_id=db_topic.id,
                    subtopic_id=f"{t_idx}{letter}",
                    specification_section_sub=f"{t_idx}.{s_idx + 1}",
                    subtopic_name=sub_data.subtopic_name,
                    description=sub_data.description,
                )
                db.add(db_subtopic)

        # Auto-add to creator's selections
        db.add(UserSpecSelection(
            user_id=user_id,
            is_guest=is_guest,
            spec_code=req.spec_code,
        ))

        db.commit()

    reload_specs()

    return {"spec_code": req.spec_code, "success": True}


@app.get("/specs/{spec_code}")
def get_spec(spec_code: str, request: Request, user=Depends(get_user)):
    """Return a single spec's full data in editable format."""
    matching_spec = allSpecs.get(spec_code)
    if matching_spec is None:
        raise HTTPException(status_code=404, detail="Specification not found")

    topics = []
    for t in matching_spec["Topics"]:
        subtopics = []
        for s in t["Sub_topics"]:
            subtopics.append({
                "subtopic_name": s["Sub_topic_name"],
                "description": s["description"],
            })
        topics.append({
            "strand": t["Strand"],
            "topic_name": t["Topic_name"],
            "subtopics": subtopics,
        })

    return {
        "qualification": matching_spec["Qualification"],
        "subject": matching_spec["Subject"],
        "exam_board": matching_spec["Exam Board"],
        "spec_code": matching_spec["Specification"],
        "optional_modules": matching_spec.get("optional_modules", False),
        "has_math": matching_spec.get("has_math", False),
        "description": matching_spec.get("description"),
        "creator_id": matching_spec.get("creator_id"),
        "is_reviewed": matching_spec.get("is_reviewed", False),
        "topics": topics,
    }


@app.put("/specs/{spec_code}")
def update_spec(spec_code: str, req: SpecCreate, request: Request, user=Depends(get_user)):
    """Update a custom specification (creator only, non-reviewed only)."""
    if user["is_authenticated"]:
        user_id = user["user_id"]
        is_guest = False
    else:
        user_id = user["guest_id"]
        is_guest = True

    with Session(engine) as db:
        db_spec = db.exec(
            select(Specification).where(Specification.spec_code == spec_code)
        ).first()
        if not db_spec:
            raise HTTPException(status_code=404, detail="Specification not found")

        if db_spec.is_reviewed:
            raise HTTPException(status_code=403, detail="Cannot edit a reviewed specification")

        if db_spec.creator_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to edit this specification")

        if len(req.topics) < 1:
            raise HTTPException(status_code=400, detail="At least one topic is required")
        for t in req.topics:
            if len(t.subtopics) < 1:
                raise HTTPException(status_code=400, detail=f"Topic '{t.topic_name}' must have at least one subtopic")

        # Update basic info
        db_spec.qualification = req.qualification
        db_spec.subject = req.subject
        db_spec.exam_board = req.exam_board
        db_spec.optional_modules = req.optional_modules
        db_spec.has_math = req.has_math
        db_spec.description = req.description

        # Delete existing topics & subtopics
        old_topics = db.exec(select(Topic).where(Topic.specification_id == db_spec.id)).all()
        for t in old_topics:
            for s in db.exec(select(Subtopic).where(Subtopic.topic_db_id == t.id)).all():
                db.delete(s)
            db.delete(t)
        db.flush()

        # Re-create topics & subtopics
        for t_idx, topic_data in enumerate(req.topics, start=1):
            db_topic = Topic(
                specification_id=db_spec.id,
                topic_id_within_spec=t_idx,
                specification_section=str(t_idx),
                strand=topic_data.strand,
                topic_name=topic_data.topic_name,
            )
            db.add(db_topic)
            db.flush()

            for s_idx, sub_data in enumerate(topic_data.subtopics):
                letter = chr(ord('a') + s_idx)
                db_subtopic = Subtopic(
                    topic_db_id=db_topic.id,
                    subtopic_id=f"{t_idx}{letter}",
                    specification_section_sub=f"{t_idx}.{s_idx + 1}",
                    subtopic_name=sub_data.subtopic_name,
                    description=sub_data.description,
                )
                db.add(db_subtopic)

        db.commit()

    reload_specs()

    return {"spec_code": spec_code, "success": True}


@app.delete("/specs/{spec_code}")
def delete_spec(spec_code: str, request: Request, user=Depends(get_user)):
    """Delete a custom specification (creator only, non-reviewed only)."""
    if user["is_authenticated"]:
        user_id = user["user_id"]
        is_guest = False
    else:
        user_id = user["guest_id"]
        is_guest = True

    with Session(engine) as db:
        db_spec = db.exec(
            select(Specification).where(Specification.spec_code == spec_code)
        ).first()
        if not db_spec:
            raise HTTPException(status_code=404, detail="Specification not found")

        if db_spec.is_reviewed:
            raise HTTPException(status_code=403, detail="Cannot delete a reviewed specification")

        if db_spec.creator_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to delete this specification")

        # Check for sessions referencing this spec
        session_count = len(db.exec(
            select(DBSess).where(DBSess.subject == spec_code)
        ).all())
        if session_count > 0:
            raise HTTPException(status_code=409, detail="Cannot delete specification with existing sessions")

        # Delete in FK order: Subtopic → Topic → Specification
        topics = db.exec(select(Topic).where(Topic.specification_id == db_spec.id)).all()
        for t in topics:
            for s in db.exec(select(Subtopic).where(Subtopic.topic_db_id == t.id)).all():
                db.delete(s)
            db.delete(t)

        # Delete user selections and module selections for this spec
        for sel in db.exec(select(UserSpecSelection).where(UserSpecSelection.spec_code == spec_code)).all():
            db.delete(sel)
        for mod in db.exec(select(UserModuleSelection).where(UserModuleSelection.spec_code == spec_code)).all():
            db.delete(mod)

        db.delete(db_spec)
        db.commit()

    reload_specs()

    return {"detail": "Specification deleted"}


@app.patch("/specs/{spec_code}/hide")
def toggle_hide_spec(spec_code: str, x_admin_secret: str = Header()):
    """Toggle the is_hidden flag on a seeded specification. Requires ADMIN_SECRET."""
    if x_admin_secret != os.environ.get("ADMIN_SECRET"):
        raise HTTPException(status_code=403, detail="Invalid admin secret")
    with Session(engine) as db:
        db_spec = db.exec(
            select(Specification).where(Specification.spec_code == spec_code)
        ).first()
        if not db_spec:
            raise HTTPException(status_code=404, detail="Specification not found")

        db_spec.is_hidden = not db_spec.is_hidden
        db.add(db_spec)
        db.commit()
        db.refresh(db_spec)
        hidden = db_spec.is_hidden

    reload_specs()
    return {"detail": f"Specification {'hidden' if hidden else 'unhidden'}", "is_hidden": hidden}


# ── User Spec Selections ──────────────────────────────────────────

@app.post("/user/specs/{spec_code}")
def add_user_spec(spec_code: str, request: Request, user=Depends(get_user)):
    """Add a specification to the user's selections."""
    if user["is_authenticated"]:
        user_id = user["user_id"]
        is_guest = False
    else:
        user_id = user["guest_id"]
        is_guest = True

    # Validate spec exists
    if spec_code not in allSpecs:
        raise HTTPException(status_code=404, detail="Specification not found")

    with Session(engine) as db:
        existing = db.exec(
            select(UserSpecSelection)
            .where(UserSpecSelection.user_id == user_id)
            .where(UserSpecSelection.is_guest == is_guest)
            .where(UserSpecSelection.spec_code == spec_code)
        ).first()
        if not existing:
            db.add(UserSpecSelection(
                user_id=user_id,
                is_guest=is_guest,
                spec_code=spec_code,
            ))
            db.commit()

    return {"success": True}


@app.delete("/user/specs/{spec_code}")
def remove_user_spec(spec_code: str, request: Request, user=Depends(get_user)):
    """Remove a specification from the user's selections."""
    if user["is_authenticated"]:
        user_id = user["user_id"]
        is_guest = False
    else:
        user_id = user["guest_id"]
        is_guest = True

    with Session(engine) as db:
        existing = db.exec(
            select(UserSpecSelection)
            .where(UserSpecSelection.user_id == user_id)
            .where(UserSpecSelection.is_guest == is_guest)
            .where(UserSpecSelection.spec_code == spec_code)
        ).first()
        if existing:
            db.delete(existing)
            db.commit()

    return {"success": True}


@app.get("/user/specs")
def get_user_specs(request: Request, user=Depends(get_user)):
    """Get only the user's selected specifications (for classify page)."""
    if user["is_authenticated"]:
        user_id = user["user_id"]
        is_guest = False
    else:
        user_id = user["guest_id"]
        is_guest = True

    with Session(engine) as db:
        selections = db.exec(
            select(UserSpecSelection)
            .where(UserSpecSelection.user_id == user_id)
            .where(UserSpecSelection.is_guest == is_guest)
        ).all()
    selected_codes = {sel.spec_code for sel in selections}

    result = []
    for code in selected_codes:
        s = allSpecs.get(code)
        if s is None:
            continue
        strands = list({t["Strand"] for t in s["Topics"]})
        tier_values = {sub.get("tier") for t in s["Topics"] for sub in t["Sub_topics"] if sub.get("tier")}
        result.append({
            "spec_code": code,
            "subject": s["Subject"],
            "exam_board": s["Exam Board"],
            "qualification": s["Qualification"],
            "optional_modules": s.get("optional_modules", False),
            "strands": sorted(strands),
            "tiers": sorted(tier_values),
            "has_tiers": len(tier_values) > 0,
        })
    return result


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
    no_spec = not req.SpecCode or req.SpecCode == "NONE"

    # Variables only populated in the spec path
    effective_strands: set[str] | None = None
    sub_topics_embed = None
    subTopicIds = None
    topk_indices = None
    similarities = None

    if not no_spec:
        matching_topic = allSpecs.get(req.SpecCode)
        if matching_topic is None:
            raise HTTPException(status_code=404, detail="Specification code not found")

        # Resolve effective strands for filtering
        if req.strands:
            effective_strands = set(req.strands)
        elif matching_topic.get("optional_modules", False):
            with Session(engine) as db:
                rows = db.exec(
                    select(UserModuleSelection)
                    .where(UserModuleSelection.user_id == user_id)
                    .where(UserModuleSelection.is_guest == is_guest)
                    .where(UserModuleSelection.spec_code == req.SpecCode)
                ).all()
                if rows:
                    effective_strands = {r.strand for r in rows}

        # Resolve effective tier for filtering
        effective_tier: str | None = None
        if req.tier:
            effective_tier = req.tier
        else:
            with Session(engine) as db:
                tier_row = db.exec(
                    select(UserTierSelection)
                    .where(UserTierSelection.user_id == user_id)
                    .where(UserTierSelection.is_guest == is_guest)
                    .where(UserTierSelection.spec_code == req.SpecCode)
                ).first()
                if tier_row:
                    effective_tier = tier_row.tier

        # Use cached embeddings for subtopics
        sub_topics_embed, subTopicIds = get_embeddings(req.SpecCode, effective_strands, effective_tier)
        if len(subTopicIds) == 0:
            raise HTTPException(status_code=400, detail="No topics match the selected strands")

        # Fill ExamBoard if missing
        if req.ExamBoard is None:
            spec_data = allSpecs.get(req.SpecCode)
            req.ExamBoard = spec_data["Exam Board"] if spec_data else "Unknown"

    question_texts = [q["text"] for q in req.question_object]
    marks = [q["marks"] for q in req.question_object]
    question_ids = [q.get("id", str(i + 1)) for i, q in enumerate(req.question_object)]

    if not no_spec:
        t0 = time.time()
        question_embed = model.encode(question_texts)
        similarities = model.similarity(sub_topics_embed, question_embed).numpy()
        print(f"Classified {len(question_texts)} questions in {time.time() - t0:.2f}s (embeddings cached)")

        k = req.num_predictions or 3
        topk_indices = np.argsort(similarities, axis=0)[-k:][::-1]
        topk_indices = list(map(list, zip(*topk_indices)))
        topk_indices = [list(map(int, row)) for row in topk_indices]

    session_id = str(uuid.uuid4())

    with Session(engine) as db:
        db_session = DBSess(
            session_id=session_id,
            exam_board=req.ExamBoard or "",
            subject=req.SpecCode or "",
            is_guest=is_guest,
            user_id=user_id,
            no_spec=no_spec,
        )
        db.add(db_session)
        db.flush()

        # Store session strands only for spec sessions
        if not no_spec and effective_strands:
            for strand in effective_strands:
                db.add(SessionStrand(session_id=session_id, strand=strand))

        for q_idx, q_text in enumerate(question_texts):
            db_question = DBQuestion(
                session_id=session_id,
                question_number=question_ids[q_idx],
                question_text=q_text,
            )
            db.add(db_question)
            db.flush()  # needed here to get db_question.id

            db_question_mark = QuestionMark(
                question_id=db_question.id,
                marks_available=marks[q_idx],
            )
            db.add(db_question_mark)

            if not no_spec:
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

        # ---------- Fetch question locations ----------
        question_locations = db.exec(
            select(QuestionLocation)
            .where(QuestionLocation.question_id.in_(question_ids))
        ).all()
        locations_by_question: dict[int, QuestionLocation] = {}
        for loc in question_locations:
            locations_by_question[loc.question_id] = loc

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
                ],

                "pdf_location": (
                    {
                        "start_page": loc.start_page,
                        "start_y": loc.start_y,
                        "end_page": loc.end_page,
                        "end_y": loc.end_y,
                    }
                    if (loc := locations_by_question.get(q.id)) else None
                ),
            })

        # ---------- Fetch session strands ----------
        session_strands_rows = db.exec(
            select(SessionStrand).where(SessionStrand.session_id == session_id)
        ).all()
        session_strands = [r.strand for r in session_strands_rows]

        # ---------- Look up spec details ----------
        spec_code = db_session.subject
        spec_data = allSpecs.get(spec_code, {})
        qualification = spec_data.get("Qualification")
        subject_name = spec_data.get("Subject")

        # ---------- Final response ----------
        return {
            "session_id": db_session.session_id,
            "name": db_session.name,
            "exam_board": db_session.exam_board,
            "spec_code": spec_code,
            "qualification": qualification,
            "subject_name": subject_name,
            "subject": db_session.subject,  # kept for backwards compatibility
            "model_name": getattr(db_session, "model_name", None),
            "created_at": db_session.created_at,
            "user_id": db_session.user_id,
            "session_strands": session_strands,
            "no_spec": db_session.no_spec,
            "has_pdf": db_session.pdf_filename is not None,
            "has_mark_scheme": db_session.mark_scheme_filename is not None,
            "paper_number": db_session.paper_number,
            "paper_name": db_session.paper_name,
            "paper_year": db_session.paper_year,
            "paper_series": db_session.paper_series,
            "questions": response_questions
        }


@app.get("/session/{session_id}/pdf")
def get_session_pdf(session_id: str, request: Request, user=Depends(get_user)):
    """Serve the original PDF file for a session."""
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
            raise HTTPException(status_code=403, detail="Not authorized to view this session")

        if not db_session.pdf_filename:
            raise HTTPException(status_code=404, detail="No PDF associated with this session")

        pdf_path = UPLOAD_DIR / db_session.pdf_filename
        if not pdf_path.exists():
            raise HTTPException(status_code=404, detail="PDF file not found")

        return FileResponse(
            path=str(pdf_path),
            media_type="application/pdf",
            filename=db_session.pdf_filename,
        )


@app.post("/session/{session_id}/mark-scheme")
async def upload_mark_scheme(session_id: str, file: UploadFile = File(...), request: Request = None, user=Depends(get_user)):
    """Upload (or replace) the mark scheme PDF for an existing session."""
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files allowed")

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

        filename = f"{session_id}_mark_scheme.pdf"
        ms_path = UPLOAD_DIR / filename
        with open(ms_path, "wb") as f:
            f.write(await file.read())

        db_session.mark_scheme_filename = filename
        db.add(db_session)
        db.commit()

    return {"success": True}


@app.get("/session/{session_id}/mark-scheme-pdf")
def get_mark_scheme_pdf(session_id: str, request: Request, user=Depends(get_user)):
    """Serve the mark scheme PDF for a session."""
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
            raise HTTPException(status_code=403, detail="Not authorized to view this session")

        if not db_session.mark_scheme_filename:
            raise HTTPException(status_code=404, detail="No mark scheme uploaded for this session")

        ms_path = UPLOAD_DIR / db_session.mark_scheme_filename
        if not ms_path.exists():
            raise HTTPException(status_code=404, detail="Mark scheme file not found")

        return FileResponse(
            path=str(ms_path),
            media_type="application/pdf",
            filename=db_session.mark_scheme_filename,
        )


@app.get("/user/sessions")
def get_user_sessions(request: Request, user=Depends(get_user), page: int = 1, page_size: int = 10):
    """
    Returns paginated sessions for authenticated users OR guests (via X-Guest-ID header).
    Includes: session_id, subject, exam_board, created_at, question_count.
    Ordered by most recent first.
    """
    with Session(engine) as db:
        if user["is_authenticated"]:
            base_query = (
                select(DBSess)
                .where(DBSess.user_id == user["user_id"])
                .where(DBSess.is_guest == False)
            )
        else:
            guest_id = user["guest_id"]
            if not guest_id:
                return {"sessions": [], "total": 0, "page": page, "page_size": page_size}
            base_query = (
                select(DBSess)
                .where(DBSess.user_id == guest_id)
                .where(DBSess.is_guest == True)
            )

        # Get total count
        total = db.exec(select(func.count()).select_from(base_query.subquery())).one()

        # Fetch paginated sessions
        offset = (page - 1) * page_size
        sessions = db.exec(
            base_query.order_by(DBSess.created_at.desc()).offset(offset).limit(page_size)
        ).all()

        if not sessions:
            return {"sessions": [], "total": total, "page": page, "page_size": page_size}

        session_ids = [s.session_id for s in sessions]

        # Bulk fetch question counts
        count_rows = db.exec(
            select(DBQuestion.session_id, func.count())
            .where(DBQuestion.session_id.in_(session_ids))
            .group_by(DBQuestion.session_id)
        ).all()
        question_counts = {row[0]: row[1] for row in count_rows}

        # Bulk fetch strands
        strand_rows = db.exec(
            select(SessionStrand.session_id, SessionStrand.strand)
            .where(SessionStrand.session_id.in_(session_ids))
        ).all()
        strands_map: dict[str, list[str]] = {}
        for sid, strand in strand_rows:
            strands_map.setdefault(sid, []).append(strand)

        result = []
        for s in sessions:
            spec = allSpecs.get(s.subject, {})
            result.append({
                "session_id": s.session_id,
                "subject": s.subject,
                "qualification": spec.get("Qualification"),
                "subject_name": spec.get("Subject"),
                "exam_board": s.exam_board,
                "created_at": s.created_at,
                "question_count": question_counts.get(s.session_id, 0),
                "strands": strands_map.get(s.session_id, []),
                "name": s.name,
                "no_spec": s.no_spec,
                "status": s.status,
                "total_marks_available": s.total_marks_available,
                "total_marks_achieved": s.total_marks_achieved,
                "paper_number": s.paper_number,
                "paper_name": s.paper_name,
                "paper_year": s.paper_year,
                "paper_series": s.paper_series,
            })

        return {"sessions": result, "total": total, "page": page, "page_size": page_size}


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

        # Migrate RevisionAttempt rows
        guest_revisions = db.exec(
            select(RevisionAttempt)
            .where(RevisionAttempt.user_id == guest_id)
            .where(RevisionAttempt.is_guest == True)
        ).all()
        for ra in guest_revisions:
            ra.user_id = user["user_id"]
            ra.is_guest = False
            db.add(ra)

        # Migrate UserSpecSelection rows
        guest_spec_sels = db.exec(
            select(UserSpecSelection)
            .where(UserSpecSelection.user_id == guest_id)
            .where(UserSpecSelection.is_guest == True)
        ).all()
        existing_user_specs = {sel.spec_code for sel in db.exec(
            select(UserSpecSelection)
            .where(UserSpecSelection.user_id == user["user_id"])
            .where(UserSpecSelection.is_guest == False)
        ).all()}
        for sel in guest_spec_sels:
            if sel.spec_code in existing_user_specs:
                db.delete(sel)  # deduplicate
            else:
                sel.user_id = user["user_id"]
                sel.is_guest = False
                db.add(sel)

        db.commit()

        return {"migrated": count}


@app.post("/upload-pdf/{SpecCode}")
async def upload_pdf(
    request: Request,
    SpecCode: str,
    file: UploadFile = File(...),
    mark_scheme: Optional[UploadFile] = File(default=None),
    strands: Optional[str] = Query(default=None, description="Comma-separated strand names"),
    tier: Optional[str] = Query(default=None, description="Tier filter: 'Higher' or 'Foundation'"),
    has_math: bool = Query(default=False),
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

    # Save optional mark scheme PDF
    mark_scheme_filename = None
    if mark_scheme is not None:
        if mark_scheme.content_type != "application/pdf":
            raise HTTPException(status_code=400, detail="Mark scheme must be a PDF")
        mark_scheme_filename = f"{job_id}_mark_scheme.pdf"
        ms_path = UPLOAD_DIR / mark_scheme_filename
        with open(ms_path, "wb") as f:
            f.write(await mark_scheme.read())

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
        strand_list,
        mark_scheme_filename,
        has_math,
        tier,
    )

    return {
        "job_id": job_id
    }

def process_pdf(job_id, SpecCode, user, strands=None, mark_scheme_filename=None, has_math=False, tier=None, paper_meta=None):
    import logging
    logger = logging.getLogger(__name__)
    pdf_path = f"Backend/uploads/pdfs/{job_id}.pdf"

    # Look up whether this spec uses math notation
    if SpecCode == "NONE":
        spec_has_math = has_math
    else:
        spec_has_math = allSpecs.get(SpecCode, {}).get("has_math", False)

    questions = None
    olmocr_workspace = None
    status_cb = lambda msg: updateStatus(job_id, msg)
    pipeline_steps = []

    if spec_has_math:
        # ── Math-aware pipeline: merge olmOCR text + PyMuPDF marks ──
        olmocr_qs = None
        pymupdf_qs = None
        ocr_source = None
        text_parser = None
        marks_parser = None

        # Step A: olmOCR for good math text (or Gemini Vision fallback)
        if OLMOCR_AVAILABLE:
            try:
                updateStatus(job_id, "Using OCR to extract equations...")
                _, olmocr_workspace = run_olmocr(pdf_path, "Backend/uploads/markdown")
                updateStatus(job_id, "OCR markdown created. Parsing questions...")
                olmocr_qs, text_parser = parse_exam_markdown(f"Backend/uploads/markdown/{job_id}.md", on_status=status_cb)
                if text_parser == "regex":
                    updateStatus(job_id, "Parsed questions with regex fallback.")
                ocr_source = "olmOCR"
                logger.info("olmOCR succeeded for math pipeline, job %s", job_id)
            except Exception as e:
                logger.warning("olmOCR failed for math pipeline, job %s: %s", job_id, e)

        if not olmocr_qs:
            try:
                updateStatus(job_id, "Using Gemini Vision for math text...")
                olmocr_qs = sort_questions(parse_pdf_with_vision(pdf_path, on_status=status_cb))
                ocr_source = "Gemini Vision"
                text_parser = "vision"
                logger.info("Gemini Vision succeeded as olmOCR fallback, job %s", job_id)
            except Exception as e:
                logger.warning("Gemini Vision fallback failed, job %s: %s", job_id, e)

        # Step B: PyMuPDF for accurate marks (write to temp dir to avoid overwriting olmOCR md)
        try:
            updateStatus(job_id, "Extracting marks from PDF...")
            md_path = extract_text_pymupdf(pdf_path, "Backend/uploads/markdown/pymupdf_tmp")
            updateStatus(job_id, "Marks markdown created. Parsing questions...")
            pymupdf_qs, marks_parser = parse_exam_markdown(str(md_path), on_status=status_cb)
            if marks_parser == "regex":
                updateStatus(job_id, "Parsed questions with regex fallback.")
            logger.info("PyMuPDF succeeded for marks, job %s", job_id)
        except Exception as e:
            logger.warning("PyMuPDF failed for marks, job %s: %s", job_id, e)

        # Step C: Merge
        if olmocr_qs and pymupdf_qs:
            questions = merge_questions(pymupdf_qs, olmocr_qs)
            pipeline_steps = [f"text: {ocr_source}({text_parser})", f"marks: PyMuPDF({marks_parser})", "merged"]
            logger.info("Merged %d questions for math pipeline, job %s", len(questions), job_id)
        elif olmocr_qs:
            questions = olmocr_qs
            pipeline_steps = [f"text: {ocr_source}({text_parser})", "single-source"]
            logger.info("Using olmOCR-only questions (PyMuPDF unavailable), job %s", job_id)
        elif pymupdf_qs:
            questions = pymupdf_qs
            pipeline_steps = [f"text+marks: PyMuPDF({marks_parser})", "single-source"]
            logger.info("Using PyMuPDF-only questions (olmOCR unavailable), job %s", job_id)
    else:
        # ── Standard pipeline (non-math): PyMuPDF → Gemini Vision → olmOCR ──
        # Try 1: PyMuPDF text extraction → LLM/regex parser
        try:
            updateStatus(job_id, "Extracting text from PDF...")
            md_path = extract_text_pymupdf(pdf_path, "Backend/uploads/markdown")
            updateStatus(job_id, "Markdown created. Parsing questions...")
            questions, parser_name = parse_exam_markdown(str(md_path), on_status=status_cb)
            if parser_name == "regex":
                updateStatus(job_id, "Parsed questions with regex fallback.")
            pipeline_steps = [f"PyMuPDF({parser_name})"]
            logger.info("PyMuPDF + parser succeeded for job %s", job_id)
        except Exception as e:
            logger.warning("PyMuPDF pipeline failed for job %s: %s", job_id, e)

        # Try 2: Gemini Vision (send PDF directly)
        if not questions:
            try:
                updateStatus(job_id, "Using Gemini Vision to extract questions...")
                questions = sort_questions(parse_pdf_with_vision(pdf_path, on_status=status_cb))
                pipeline_steps = ["Gemini Vision"]
                logger.info("Gemini Vision succeeded for job %s", job_id)
            except Exception as e:
                logger.warning("Gemini Vision failed for job %s: %s", job_id, e)

        # Try 3: Legacy olmOCR fallback
        if not questions and OLMOCR_AVAILABLE:
            try:
                updateStatus(job_id, "Using OCR to process PDF...")
                _, olmocr_workspace = run_olmocr(pdf_path, "Backend/uploads/markdown")
                updateStatus(job_id, "OCR complete. Parsing questions...")
                questions, parser_name = parse_exam_markdown(f"Backend/uploads/markdown/{job_id}.md", on_status=status_cb)
                if parser_name == "regex":
                    updateStatus(job_id, "Parsed questions with regex fallback.")
                pipeline_steps = [f"olmOCR({parser_name})"]
                logger.info("olmOCR fallback succeeded for job %s", job_id)
            except Exception as e:
                logger.warning("olmOCR fallback failed for job %s: %s", job_id, e)

    if not questions:
        updateStatus(job_id, "Error: Failed to extract questions from PDF")
        return

    pipeline_info = " | ".join(pipeline_steps) if pipeline_steps else None

    updateStatus(job_id, "Questions extracted. Classifying questions by topic...")

    if user["is_authenticated"]:
        user_id = user["user_id"]
        is_guest = False
    else:
        user_id = user["guest_id"]
        is_guest = True

    classify_spec_code = None if SpecCode == "NONE" else SpecCode
    session_id = classify_questions_logic(classificationRequest(question_object=questions, SpecCode=classify_spec_code, strands=strands, tier=tier), user_id=user_id, is_guest=is_guest)["session_id"]

    # Store PDF filename (and optional mark scheme) and locate questions in the PDF
    try:
        with Session(engine) as db:
            db_session = db.exec(select(DBSess).where(DBSess.session_id == session_id)).first()
            if db_session:
                db_session.pdf_filename = f"{job_id}.pdf"
                if mark_scheme_filename:
                    db_session.mark_scheme_filename = mark_scheme_filename
                if paper_meta:
                    db_session.paper_number = paper_meta.get("paper_number")
                    db_session.paper_name = paper_meta.get("paper_name")
                    db_session.paper_year = paper_meta.get("year")
                    db_session.paper_series = paper_meta.get("series")
                db.add(db_session)
                db.commit()

        locations = locate_questions_in_pdf(pdf_path, questions, workspace_path=olmocr_workspace)
        if locations:
            with Session(engine) as db:
                # Map question numbers to DB question IDs
                db_questions = db.exec(
                    select(DBQuestion).where(DBQuestion.session_id == session_id)
                ).all()
                qnum_to_dbid = {q.question_number: q.id for q in db_questions}

                for loc in locations:
                    db_qid = qnum_to_dbid.get(loc["question_id"])
                    if db_qid is None:
                        continue
                    db.add(QuestionLocation(
                        question_id=db_qid,
                        start_page=loc["start_page"],
                        start_y=loc["start_y"],
                        end_page=loc["end_page"],
                        end_y=loc["end_y"],
                    ))
                db.commit()
            logger.info("Stored %d question locations for session %s", len(locations), session_id)
    except Exception as e:
        logger.warning("Question location failed for job %s: %s", job_id, e)

    updateStatus(job_id, "Done", session_id, pipeline=pipeline_info)

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
    matching_spec = allSpecs.get(spec_code)
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

        spec_lookup = allSpecs

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
                if m and m.marks_available:
                    total_available += m.marks_available
                    if m.marks_achieved is not None:
                        total_achieved += m.marks_achieved
                        has_any_marks = True

            # Look up spec details
            spec_info = spec_lookup.get(s.subject, {})
            subject_name = spec_info.get("Subject")

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
            if not m or m.marks_achieved is None or not m.marks_available:
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

        # Count distinct strands per spec in a single query
        spec_codes = list({s.subject for s in sessions})
        strands_per_spec: dict[str, int] = {}
        if spec_codes:
            strand_count_rows = db.exec(
                select(Specification.spec_code, func.count(Topic.strand.distinct()))
                .join(Topic, Topic.specification_id == Specification.id)
                .where(Specification.spec_code.in_(spec_codes))
                .group_by(Specification.spec_code)
            ).all()
            strands_per_spec = {row[0]: row[1] for row in strand_count_rows}

        # Build user_module_selections for optional_modules specs
        user_module_selections: dict[str, list[str]] = {}
        if user["is_authenticated"]:
            uid = user["user_id"]
            is_g = False
        else:
            uid = user["guest_id"]
            is_g = True

        optional_spec_codes = [
            sc for sc in spec_codes
            if spec_lookup.get(sc, {}).get("optional_modules", False)
        ]
        if optional_spec_codes:
            mod_rows = db.exec(
                select(UserModuleSelection)
                .where(UserModuleSelection.user_id == uid)
                .where(UserModuleSelection.is_guest == is_g)
                .where(UserModuleSelection.spec_code.in_(optional_spec_codes))
            ).all()
            for r in mod_rows:
                user_module_selections.setdefault(r.spec_code, []).append(r.strand)

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
    matching_spec = allSpecs.get(spec_code)
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
            for loc in db.exec(select(QuestionLocation).where(QuestionLocation.question_id.in_(question_ids))).all():
                db.delete(loc)
            for ra in db.exec(select(RevisionAttempt).where(RevisionAttempt.question_id.in_(question_ids))).all():
                db.delete(ra)
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


class SessionNameBody(BaseModel):
    name: str | None = None

@app.patch("/session/{session_id}/name")
def rename_session(session_id: str, body: SessionNameBody, request: Request, user=Depends(get_user)):
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
            raise HTTPException(status_code=403, detail="Not authorized to rename this session")

        db_session.name = body.name
        db.add(db_session)
        db.commit()

    return {"session_id": session_id, "name": body.name}


# ── Revision endpoints ──────────────────────────────────────────────

@app.get("/revision/pool")
def get_revision_pool(
    request: Request,
    spec_code: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    user=Depends(get_user),
):
    uid = user["user_id"] if user["is_authenticated"] else user["guest_id"]
    is_guest = not user["is_authenticated"]

    with Session(engine) as db:
        # Base query: questions where marks_achieved < marks_available, owned by user
        base = (
            select(
                DBQuestion.id,
                DBQuestion.question_number,
                DBQuestion.question_text,
                QuestionMark.marks_available,
                QuestionMark.marks_achieved,
                DBSess.session_id,
                DBSess.subject,
                DBSess.exam_board,
                DBSess.pdf_filename,
                DBSess.mark_scheme_filename,
            )
            .join(DBSess, DBQuestion.session_id == DBSess.session_id)
            .join(QuestionMark, QuestionMark.question_id == DBQuestion.id)
            .where(DBSess.user_id == uid)
            .where(DBSess.is_guest == is_guest)
            .where(QuestionMark.marks_available.isnot(None))
            .where(QuestionMark.marks_achieved.isnot(None))
            .where(QuestionMark.marks_achieved < QuestionMark.marks_available)
        )

        # Subquery: latest revision attempt per question for this user
        latest_attempt = (
            select(
                RevisionAttempt.question_id,
                func.max(RevisionAttempt.id).label("max_id"),
            )
            .where(RevisionAttempt.user_id == uid)
            .where(RevisionAttempt.is_guest == is_guest)
            .group_by(RevisionAttempt.question_id)
            .subquery()
        )

        # Exclude questions whose latest attempt has full marks
        full_marks_qids = (
            select(RevisionAttempt.question_id)
            .join(latest_attempt, RevisionAttempt.id == latest_attempt.c.max_id)
            .where(RevisionAttempt.marks_achieved >= RevisionAttempt.marks_available)
            .subquery()
        )

        pool_query = base.where(DBQuestion.id.notin_(select(full_marks_qids.c.question_id)))

        # Get all distinct spec_codes across the full pool (before filtering)
        all_spec_codes = db.exec(
            select(DBSess.subject)
            .distinct()
            .join(DBQuestion, DBQuestion.session_id == DBSess.session_id)
            .join(QuestionMark, QuestionMark.question_id == DBQuestion.id)
            .where(DBSess.user_id == uid)
            .where(DBSess.is_guest == is_guest)
            .where(QuestionMark.marks_available.isnot(None))
            .where(QuestionMark.marks_achieved.isnot(None))
            .where(QuestionMark.marks_achieved < QuestionMark.marks_available)
            .where(DBQuestion.id.notin_(select(full_marks_qids.c.question_id)))
        ).all()

        # Apply spec_code filter if provided
        if spec_code:
            pool_query = pool_query.where(DBSess.subject == spec_code)

        # Get total count (with filter applied)
        count_rows = db.exec(pool_query).all()
        total_count = len(count_rows)

        # Get random batch
        rows = db.exec(pool_query.order_by(func.random()).limit(limit)).all()

        # Build response with full context
        q_ids = [row[0] for row in rows]

        # Bulk fetch locations, predictions, corrections
        if q_ids:
            all_locs = db.exec(
                select(QuestionLocation).where(QuestionLocation.question_id.in_(q_ids))
            ).all()
            locs_by_q = {loc.question_id: loc for loc in all_locs}

            all_preds = db.exec(
                select(DBPrediction)
                .where(DBPrediction.question_id.in_(q_ids))
                .order_by(DBPrediction.rank)
            ).all()
            preds_by_q: dict[int, list] = {}
            for p in all_preds:
                preds_by_q.setdefault(p.question_id, []).append(p)

            all_corrections = db.exec(
                select(UserCorrection).where(UserCorrection.question_id.in_(q_ids))
            ).all()
            corrections_by_q: dict[int, list] = {}
            for c in all_corrections:
                corrections_by_q.setdefault(c.question_id, []).append(c)
        else:
            locs_by_q = {}
            preds_by_q = {}
            corrections_by_q = {}

        questions = []
        for row in rows:
            q_id = row[0]

            loc = locs_by_q.get(q_id)
            pdf_location = None
            if loc:
                pdf_location = {
                    "start_page": loc.start_page,
                    "start_y": loc.start_y,
                    "end_page": loc.end_page,
                    "end_y": loc.end_y,
                }

            predictions = [
                {
                    "rank": p.rank,
                    "strand": p.strand,
                    "topic": p.topic,
                    "subtopic": p.subtopic,
                    "spec_sub_section": p.spec_sub_section,
                    "similarity_score": p.similarity_score,
                    "description": p.description,
                }
                for p in preds_by_q.get(q_id, [])
            ]

            user_corrections = [
                {
                    "subtopic_id": c.subtopic_id,
                    "strand": c.strand,
                    "topic": c.topic,
                    "subtopic": c.subtopic,
                    "spec_sub_section": c.spec_sub_section,
                    "description": c.description,
                }
                for c in corrections_by_q.get(q_id, [])
            ]

            questions.append({
                "question_id": q_id,
                "question_number": row[1],
                "question_text": row[2],
                "marks_available": row[3],
                "original_marks_achieved": row[4],
                "session_id": row[5],
                "spec_code": row[6],
                "exam_board": row[7],
                "has_pdf": row[8] is not None,
                "has_mark_scheme": row[9] is not None,
                "pdf_location": pdf_location,
                "predictions": predictions,
                "user_corrections": user_corrections,
            })

        return {
            "total_count": total_count,
            "spec_codes": all_spec_codes,
            "questions": questions,
        }


class RevisionAttemptRequest(BaseModel):
    marks_achieved: int


@app.post("/revision/{question_id}/attempt")
def record_revision_attempt(
    question_id: int,
    body: RevisionAttemptRequest,
    request: Request,
    user=Depends(get_user),
):
    uid = user["user_id"] if user["is_authenticated"] else user["guest_id"]
    is_guest = not user["is_authenticated"]

    with Session(engine) as db:
        # Validate question exists and belongs to user
        row = db.exec(
            select(DBQuestion, QuestionMark)
            .join(DBSess, DBQuestion.session_id == DBSess.session_id)
            .join(QuestionMark, QuestionMark.question_id == DBQuestion.id)
            .where(DBQuestion.id == question_id)
            .where(DBSess.user_id == uid)
            .where(DBSess.is_guest == is_guest)
        ).first()

        if not row:
            raise HTTPException(status_code=404, detail="Question not found")

        question, mark = row
        marks_available = mark.marks_available or 0

        if body.marks_achieved < 0 or body.marks_achieved > marks_available:
            raise HTTPException(
                status_code=400,
                detail=f"marks_achieved must be between 0 and {marks_available}",
            )

        attempt = RevisionAttempt(
            question_id=question_id,
            user_id=uid,
            is_guest=is_guest,
            marks_achieved=body.marks_achieved,
            marks_available=marks_available,
        )
        db.add(attempt)
        db.commit()

        return {
            "success": True,
            "is_full_marks": body.marks_achieved >= marks_available,
        }


# ── Past Papers Library ───────────────────────────────────────────────────────

def _index_past_papers(spec_code: str) -> None:
    """Fetch AQA API metadata for spec_code and upsert into PastPaper table (no downloads)."""
    import logging
    logger = logging.getLogger(__name__)
    # Look up subject from the Specification table; fall back to config or "Unknown"
    with Session(engine) as db:
        spec_row = db.exec(select(Specification).where(Specification.spec_code == spec_code)).first()
    subject = spec_row.subject if spec_row else aqa_scraper_config.SPECS.get(spec_code, "Unknown")
    http = requests.Session()
    http.headers["User-Agent"] = "TopicTracker/1.0 Educational"
    results = aqa_fetch_all_results(spec_code, http)
    with Session(engine) as db:
        for result in results:
            entry = aqa_build_entry(result, spec_code, subject)
            if entry["paper_type"] not in ("QP", "MS") or entry.get("is_modified"):
                continue
            existing = db.get(PastPaper, entry["content_id"])
            if existing:
                existing.local_path = entry["local_path"]
                existing.source_url = entry["source_url"]
                existing.scraped_at = entry["scraped_at"]
                existing.tier = entry.get("tier")
                existing.paper_name = entry.get("paper_name")
                db.add(existing)
            else:
                db.add(PastPaper(
                    content_id=entry["content_id"],
                    spec_code=entry["spec_code"],
                    subject=entry["subject"],
                    year=entry["year"],
                    series=entry["series"],
                    paper_type=entry["paper_type"],
                    paper_number=entry["paper_number"],
                    paper_name=entry.get("paper_name"),
                    tier=entry.get("tier"),
                    filename=entry["filename"],
                    local_path=entry["local_path"],
                    source_url=entry["source_url"],
                    file_size_kb=entry["file_size_kb"],
                    scraped_at=entry["scraped_at"],
                ))
        db.commit()
    logger.info("Indexed past papers for spec %s (%d results)", spec_code, len(results))


def _index_past_papers_edexcel(spec_code: str) -> None:
    """Fetch Edexcel Algolia metadata for spec_code and upsert into PastPaper table (no downloads)."""
    import logging
    logger = logging.getLogger(__name__)
    if spec_code not in edexcel_scraper_config.SPECS:
        logger.warning("No Edexcel config for spec %s; skipping index", spec_code)
        return
    spec_cfg = edexcel_scraper_config.SPECS[spec_code]
    http = requests.Session()
    http.headers["User-Agent"] = "TopicTracker/1.0 Educational"
    hits = edexcel_fetch_all_hits(spec_cfg["algolia_code"], http)
    with Session(engine) as db:
        for hit in hits:
            entry = edexcel_parse_hit(hit, spec_code, spec_cfg)
            if entry is None:
                continue
            existing = db.get(PastPaper, entry["content_id"])
            if existing:
                existing.local_path = entry["local_path"]
                existing.source_url = entry["source_url"]
                existing.scraped_at = entry["scraped_at"]
                if entry.get("file_size_kb") is not None:
                    existing.file_size_kb = entry["file_size_kb"]
                db.add(existing)
            else:
                db.add(PastPaper(
                    content_id=entry["content_id"],
                    spec_code=entry["spec_code"],
                    subject=entry["subject"],
                    year=entry["year"],
                    series=entry["series"],
                    paper_type=entry["paper_type"],
                    paper_number=entry.get("paper_number"),
                    paper_name=entry.get("paper_name"),
                    tier=entry.get("tier"),
                    filename=entry["filename"],
                    local_path=entry["local_path"],
                    source_url=entry["source_url"],
                    file_size_kb=entry.get("file_size_kb"),
                    scraped_at=entry["scraped_at"],
                ))
        db.commit()
    logger.info("Indexed Edexcel past papers for spec %s (%d hits)", spec_code, len(hits))


def _index_past_papers_ocr(spec_code: str) -> None:
    """Fetch OCR resource-filter metadata for spec_code and upsert into PastPaper table (no downloads)."""
    import logging
    logger = logging.getLogger(__name__)
    if spec_code not in ocr_scraper_config.SPECS:
        logger.warning("No OCR config for spec %s; skipping index", spec_code)
        return
    spec_cfg = ocr_scraper_config.SPECS[spec_code]
    http = requests.Session()
    http.headers["User-Agent"] = "TopicTracker/1.0 Educational"
    html = ocr_fetch_resources_html(
        spec_cfg["qualification_value"],
        spec_cfg["level"],
        spec_cfg.get("page_id", ""),
        http,
    )
    raw_items = ocr_parse_resources_html(html)
    with Session(engine) as db:
        for item in raw_items:
            entry = ocr_build_entry(item, spec_code, spec_cfg)
            if entry is None:
                continue
            existing = db.get(PastPaper, entry["content_id"])
            if existing:
                existing.local_path = entry["local_path"]
                existing.source_url = entry["source_url"]
                existing.scraped_at = entry["scraped_at"]
                if entry.get("file_size_kb") is not None:
                    existing.file_size_kb = entry["file_size_kb"]
                db.add(existing)
            else:
                db.add(PastPaper(
                    content_id=entry["content_id"],
                    spec_code=entry["spec_code"],
                    subject=entry["subject"],
                    year=entry["year"],
                    series=entry["series"],
                    paper_type=entry["paper_type"],
                    paper_number=entry.get("paper_number"),
                    paper_name=entry.get("paper_name"),
                    tier=entry.get("tier"),
                    filename=entry["filename"],
                    local_path=entry["local_path"],
                    source_url=entry["source_url"],
                    file_size_kb=entry.get("file_size_kb"),
                    scraped_at=entry["scraped_at"],
                ))
        db.commit()
    logger.info("Indexed OCR past papers for spec %s (%d items)", spec_code, len(raw_items))


@app.get("/past-papers")
def get_past_papers(
    spec_code: str = Query(..., description="Specification code to list papers for"),
    request: Request = None,
    user=Depends(get_user),
):
    """Return all QP entries for a spec with their matched MS content_id attached.
    Auto-indexes from the exam board API on first request for a spec."""
    # Auto-populate if this spec has never been indexed
    with Session(engine) as db:
        has_any = db.exec(
            select(PastPaper).where(PastPaper.spec_code == spec_code).limit(1)
        ).first()

    if has_any is None:
        exam_board = allSpecs.get(spec_code, {}).get("Exam Board", "")
        if exam_board == "Edexcel":
            _index_past_papers_edexcel(spec_code)
        elif exam_board == "OCR":
            _index_past_papers_ocr(spec_code)
        else:
            _index_past_papers(spec_code)

    with Session(engine) as db:
        qps = db.exec(
            select(PastPaper)
            .where(PastPaper.spec_code == spec_code)
            .where(PastPaper.paper_type == "QP")
        ).all()

        mss = db.exec(
            select(PastPaper)
            .where(PastPaper.spec_code == spec_code)
            .where(PastPaper.paper_type == "MS")
        ).all()

    # Build lookup: (year, series, paper_number, tier) → MS content_id
    # Also build a fallback by paper_name for when paper_number is missing on one side.
    ms_lookup: dict[tuple, str] = {}
    ms_name_lookup: dict[tuple, str] = {}  # (year, series, paper_name, tier)
    for ms in mss:
        key = (ms.year, ms.series, ms.paper_number, ms.tier)
        ms_lookup[key] = ms.content_id
        if ms.paper_name:
            name_key = (ms.year, ms.series, ms.paper_name, ms.tier)
            ms_name_lookup[name_key] = ms.content_id

    papers = []
    for qp in qps:
        ms_content_id = ms_lookup.get((qp.year, qp.series, qp.paper_number, qp.tier))
        # Fallback: match by paper_name when paper_number is missing on either side
        if ms_content_id is None and qp.paper_name:
            ms_content_id = ms_name_lookup.get((qp.year, qp.series, qp.paper_name, qp.tier))
        papers.append({
            "content_id": qp.content_id,
            "spec_code": qp.spec_code,
            "subject": qp.subject,
            "year": qp.year,
            "series": qp.series,
            "paper_number": qp.paper_number,
            "paper_name": qp.paper_name,
            "tier": qp.tier,
            "filename": qp.filename,
            "source_url": qp.source_url,
            "ms_content_id": ms_content_id,
        })

    # Sort: newest first, then series, then paper number
    papers.sort(key=lambda p: (-(p["year"] or 0), p["series"] or "", p["paper_number"] or ""))
    return papers


class ClassifyPastPaperRequest(BaseModel):
    content_id: str
    strands: Optional[List[str]] = None
    tier: Optional[str] = None
    include_ms: bool = True


@app.post("/classify-past-paper/{SpecCode}")
async def classify_past_paper(
    SpecCode: str,
    req: ClassifyPastPaperRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    user=Depends(get_user),
):
    """Download a past paper on-demand and run it through the existing PDF pipeline."""
    with Session(engine) as db:
        paper = db.get(PastPaper, req.content_id)
        if not paper:
            raise HTTPException(status_code=404, detail="Paper not found in index. Run populate_db first.")

    local_path = Path(paper.local_path)

    # Download QP if not already cached
    if not local_path.exists():
        try:
            http = requests.Session()
            http.headers["User-Agent"] = "TopicTracker/1.0 Educational"
            scraper_download_pdf(paper.source_url, str(local_path), http, delay_s=0)
            size_kb = local_path.stat().st_size / 1024
            with Session(engine) as db:
                p = db.get(PastPaper, req.content_id)
                if p:
                    p.file_size_kb = round(size_kb, 2)
                    db.add(p)
                    db.commit()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Failed to download paper: {e}")

    # Copy to UPLOAD_DIR so process_pdf can find it
    job_id = str(uuid.uuid4())
    dest_path = UPLOAD_DIR / f"{job_id}.pdf"
    shutil.copy2(str(local_path), str(dest_path))

    # Optionally find and download the matching mark scheme
    mark_scheme_filename = None
    if req.include_ms:
        with Session(engine) as db:
            ms = db.exec(
                select(PastPaper)
                .where(PastPaper.spec_code == paper.spec_code)
                .where(PastPaper.year == paper.year)
                .where(PastPaper.series == paper.series)
                .where(PastPaper.paper_number == paper.paper_number)
                .where(PastPaper.paper_type == "MS")
            ).first()

        if ms:
            ms_local = Path(ms.local_path)
            if not ms_local.exists():
                try:
                    http = requests.Session()
                    http.headers["User-Agent"] = "TopicTracker/1.0 Educational"
                    scraper_download_pdf(ms.source_url, str(ms_local), http, delay_s=0)
                except Exception:
                    pass  # mark scheme is optional; don't fail the whole request

            if ms_local.exists():
                mark_scheme_filename = f"{job_id}_mark_scheme.pdf"
                shutil.copy2(str(ms_local), str(UPLOAD_DIR / mark_scheme_filename))

    # Write initial status
    status = {"job_id": job_id, "status": "Preparing paper...", "session_id": None}
    with open(f"Backend/uploads/status/{job_id}.json", "w") as f:
        json.dump(status, f)

    paper_meta = {
        "paper_number": paper.paper_number,
        "paper_name": paper.paper_name,
        "year": paper.year,
        "series": paper.series,
    }

    background_tasks.add_task(
        process_pdf,
        job_id,
        SpecCode,
        user,
        req.strands,
        mark_scheme_filename,
        False,   # has_math — determined from spec inside process_pdf
        req.tier,
        paper_meta,
    )

    return {"job_id": job_id}
