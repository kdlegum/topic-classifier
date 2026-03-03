"""PDF classification result caching.

Avoids re-running OCR + classification for previously seen papers.
Cache entries are invalidated when the embedding hash or parser version changes.
"""

import json
import logging
import re
import time
import uuid
from datetime import datetime

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from Backend.sessionDatabase import (
    Session as DBSess,
    Question as DBQuestion,
    Prediction as DBPrediction,
    QuestionMark,
    SessionStrand,
    QuestionLocation,
    CachedPaper,
)
from Backend.database import engine
from Backend.embedding_cache import get_spec_embedding_hash

logger = logging.getLogger(__name__)

# Bump this when OCR/parsing logic changes to invalidate all existing cache entries
PARSER_VERSION = 1


# ── Eligibility checks ───────────────────────────────────────────────────────

def check_cache_eligibility(questions, locations, spec_has_math, pipeline_used):
    """Return (eligible: bool, reason: str | None). All checks must pass."""
    pipeline_used = pipeline_used or ""

    # 1. Math papers must have gone through olmOCR for quality text
    if spec_has_math and "olmOCR" not in pipeline_used:
        return False, "math_without_olmocr"

    # 2. All marks must be present
    if any(q.get("marks") is None for q in questions):
        return False, "missing_marks"

    # 3. Question numbers must appear in non-decreasing order
    if not _questions_in_order([q["id"] for q in questions]):
        return False, "questions_out_of_order"

    # 4. Coordinates (if present) must also be in document order
    if locations and not _coordinates_in_order(locations):
        return False, "coordinates_out_of_order"

    return True, None


def _questions_in_order(question_ids) -> bool:
    """Extract leading integer from each ID and check non-decreasing."""
    nums = []
    for qid in question_ids:
        m = re.match(r'^[Qq]?(\d+)', str(qid))
        if m:
            nums.append(int(m.group(1)))
    for i in range(1, len(nums)):
        if nums[i] < nums[i - 1]:
            return False
    return True


def _coordinates_in_order(locations) -> bool:
    """Check consecutive locations are in document reading order."""
    for i in range(len(locations) - 1):
        curr = (locations[i]["start_page"], locations[i]["start_y"])
        nxt = (locations[i + 1]["start_page"], locations[i + 1]["start_y"])
        if nxt < curr:
            return False
    return True


# ── Cache read/write ─────────────────────────────────────────────────────────

def get_cached_paper(pdf_hash: str, spec_code: str, strands_key, tier) -> CachedPaper | None:
    """Return a valid cached paper row, or None on miss/stale."""
    with Session(engine) as db:
        row = db.exec(
            select(CachedPaper)
            .where(CachedPaper.pdf_hash == pdf_hash)
            .where(CachedPaper.spec_code == spec_code)
            .where(CachedPaper.strands_key == strands_key)
            .where(CachedPaper.tier == tier)
        ).first()

        if row is None:
            return None

        # Validity: parser version
        if row.parser_version != PARSER_VERSION:
            db.delete(row)
            db.commit()
            logger.info("Cache miss (parser version changed) for pdf_hash=%.8s", pdf_hash)
            return None

        # Validity: embedding hash
        current_emb_hash = get_spec_embedding_hash(spec_code)
        if current_emb_hash != row.embedding_hash:
            db.delete(row)
            db.commit()
            logger.info("Cache miss (embedding hash changed) for pdf_hash=%.8s", pdf_hash)
            return None

        return row


def save_cached_paper(
    pdf_hash: str,
    spec_code: str,
    effective_strands,
    effective_tier,
    session_id: str,
    questions: list,
    locations: list,
    pipeline_used,
    spec_has_math: bool,
):
    """Persist classification results to cache if quality checks pass."""
    eligible, reason = check_cache_eligibility(questions, locations, spec_has_math, pipeline_used)
    if not eligible:
        logger.info("Paper not cached (reason=%s) for session %s", reason, session_id)
        return

    strands_key = ",".join(sorted(effective_strands)) if effective_strands else None

    with Session(engine) as db:
        # Read predictions from DB and serialize by question number
        db_questions = db.exec(
            select(DBQuestion).where(DBQuestion.session_id == session_id)
        ).all()

        predictions_data = []
        for dbq in db_questions:
            preds = db.exec(
                select(DBPrediction)
                .where(DBPrediction.question_id == dbq.id)
                .order_by(DBPrediction.rank)
            ).all()
            predictions_data.append({
                "question_id": dbq.question_number,
                "predictions": [
                    {
                        "rank": p.rank,
                        "strand": p.strand,
                        "topic": p.topic,
                        "subtopic": p.subtopic,
                        "spec_sub_section": p.spec_sub_section,
                        "similarity_score": p.similarity_score,
                        "description": p.description,
                    }
                    for p in preds
                ],
            })

        embedding_hash = get_spec_embedding_hash(spec_code) or ""

        cached = CachedPaper(
            pdf_hash=pdf_hash,
            spec_code=spec_code,
            strands_key=strands_key,
            tier=effective_tier,
            embedding_hash=embedding_hash,
            parser_version=PARSER_VERSION,
            questions_json=json.dumps(questions),
            locations_json=json.dumps(locations) if locations else None,
            predictions_json=json.dumps(predictions_data),
            pipeline_used=pipeline_used or "",
        )

        try:
            db.add(cached)
            db.commit()
            logger.info("Cached paper pdf_hash=%.8s spec=%s", pdf_hash, spec_code)
        except IntegrityError:
            db.rollback()
            logger.info("Cache duplicate (race condition) for pdf_hash=%.8s", pdf_hash)


# ── Session cloning ──────────────────────────────────────────────────────────

def clone_session_from_cache(
    cached: CachedPaper,
    user_id: str,
    is_guest: bool,
    exam_board: str,
    strands,
    job_id: str,
    mark_scheme_filename,
    paper_meta,
) -> str:
    """Create a new session by replaying cached questions/predictions/locations."""
    questions = json.loads(cached.questions_json)
    locations = json.loads(cached.locations_json) if cached.locations_json else []
    predictions_list = json.loads(cached.predictions_json)

    preds_by_qid = {p["question_id"]: p["predictions"] for p in predictions_list}
    loc_by_qid = {loc["question_id"]: loc for loc in locations}

    session_id = str(uuid.uuid4())

    t0 = time.time()

    with Session(engine) as db:
        db_session = DBSess(
            session_id=session_id,
            exam_board=exam_board,
            subject=cached.spec_code,
            is_guest=is_guest,
            user_id=user_id,
            pdf_filename=f"{job_id}.pdf",
            mark_scheme_filename=mark_scheme_filename,
        )
        if paper_meta:
            db_session.paper_number = paper_meta.get("paper_number")
            db_session.paper_name = paper_meta.get("paper_name")
            db_session.paper_year = paper_meta.get("year")
            db_session.paper_series = paper_meta.get("series")
        db.add(db_session)
        db.flush()

        if strands:
            for strand in strands:
                db.add(SessionStrand(session_id=session_id, strand=strand))

        # Add all questions first, then single flush to get all IDs at once
        db_questions_list = []
        for q in questions:
            db_question = DBQuestion(
                session_id=session_id,
                question_number=q["id"],
                question_text=q["text"],
            )
            db_questions_list.append((db_question, q))
            db.add(db_question)

        db.flush()  # single flush — populates all db_question.id values

        # Build all related records in one pass now that IDs are available
        related = []
        for db_question, q in db_questions_list:
            related.append(QuestionMark(
                question_id=db_question.id,
                marks_available=q.get("marks"),
            ))
            for pred in preds_by_qid.get(q["id"], []):
                related.append(DBPrediction(
                    question_id=db_question.id,
                    rank=pred["rank"],
                    strand=pred["strand"],
                    topic=pred["topic"],
                    subtopic=pred["subtopic"],
                    spec_sub_section=pred["spec_sub_section"],
                    similarity_score=pred["similarity_score"],
                    description=pred["description"],
                ))
            loc = loc_by_qid.get(q["id"])
            if loc:
                related.append(QuestionLocation(
                    question_id=db_question.id,
                    start_page=loc["start_page"],
                    start_y=loc["start_y"],
                    end_page=loc["end_page"],
                    end_y=loc["end_y"],
                ))

        db.add_all(related)

        # Increment hit counter in the same transaction — no second session needed
        db.execute(
            update(CachedPaper)
            .where(CachedPaper.id == cached.id)
            .values(hit_count=CachedPaper.hit_count + 1)
        )

        db.commit()

    elapsed = time.time() - t0
    logger.info(
        "Cache clone took %.3fs for %d questions (session=%s, hit_count=%d)",
        elapsed, len(questions), session_id, cached.hit_count + 1,
    )
    return session_id
