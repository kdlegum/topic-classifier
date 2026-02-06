"""
Seed script: creates a test guest user with 6 sessions for analytics testing.
Run from Backend/ directory:  python seed_test_user.py

Idempotent — deletes existing test-user-analytics data first.
"""

import uuid
import json
from datetime import datetime, timedelta
from sqlmodel import Session, create_engine, select, SQLModel
from sessionDatabase import Session as DBSess, Question as DBQuestion, Prediction as DBPrediction, QuestionMark

GUEST_ID = "test-user-analytics"
ENGINE = create_engine("sqlite:///exam_app.db")
SQLModel.metadata.create_all(ENGINE)

with open("subtopics_index.json", "r", encoding="utf-8") as f:
    subtopics_index = json.load(f)


def lookup(board: str, spec: str, subtopic_id: str):
    key = f"{board}_{spec}_{subtopic_id}"
    info = subtopics_index[key]
    return {
        "strand": info["strand"],
        "topic": info["topic_name"],
        "subtopic": info["name"],
        "spec_sub_section": info["spec_sub_section"],
        "description": info["description"],
    }


# ── Session definitions ──────────────────────────────────────────────

SESSIONS = [
    # Session 1: OCR H240, 8 questions, ~70%
    {
        "board": "OCR", "spec": "H240",
        "questions": [
            # (question_text, marks_available, marks_achieved, subtopic_id)
            ("Prove by contradiction that sqrt(2) is irrational.", 5, 4, "1d"),
            ("Simplify the following expression using laws of indices.", 4, 3, "2a"),
            ("Find the equation of the tangent to the curve.", 6, 4, "3a"),
            ("Find the sum of the first 20 terms of the arithmetic series.", 5, 4, "4a"),
            ("Solve the trigonometric equation in the range 0 to 2pi.", 6, 4, "5a"),
            ("Solve the equation 3^x = 15.", 4, 3, "6a"),
            ("Find the mean and standard deviation of the data set.", 5, 3, "12a"),
            ("A particle moves along a straight line. Find its velocity.", 5, 4, "17a"),
        ],
    },
    # Session 2: OCR H240, 6 questions, ~50%
    {
        "board": "OCR", "spec": "H240",
        "questions": [
            ("Differentiate y = x^3 + 2x using first principles.", 6, 3, "7a"),
            ("Find the integral of (3x^2 + 1) dx.", 5, 2, "8a"),
            ("Use the Newton-Raphson method to find a root.", 6, 3, "9a"),
            ("Find the magnitude and direction of the resultant vector.", 5, 3, "10a"),
            ("Calculate the probability of event A given B.", 6, 3, "13a"),
            ("Test the hypothesis that the mean is 50.", 6, 3, "15a"),
        ],
    },
    # Session 3: OCR H240, 10 questions, ~80%
    {
        "board": "OCR", "spec": "H240",
        "questions": [
            ("Show by counter example that the statement is false.", 4, 4, "1c"),
            ("Rationalise the denominator of the expression.", 3, 3, "2b"),
            ("Find the distance between two points.", 4, 3, "3b"),
            ("Find the nth term of the geometric sequence.", 5, 4, "4c"),
            ("Prove the trigonometric identity.", 5, 4, "5c"),
            ("Sketch the graph of y = e^x + 2.", 3, 3, "6b"),
            ("A random sample of size 30 is taken. Explain why this is suitable.", 3, 2, "11a"),
            ("Interpret the scatter diagram and comment on correlation.", 4, 3, "12b"),
            ("Find the resultant force on the particle.", 6, 5, "18a"),
            ("Calculate the moment about point A.", 5, 4, "19a"),
        ],
    },
    # Session 4: Edexcel 9PH0, 8 questions, ~60%
    {
        "board": "Edexcel", "spec": "9PH0",
        "questions": [
            ("Describe how to measure the acceleration due to gravity.", 6, 4, "2a"),
            ("Calculate the resistance of the circuit.", 5, 3, "3a"),
            ("Explain the stress-strain graph for a ductile material.", 6, 3, "4a"),
            ("Describe the properties of a transverse wave.", 5, 3, "5a"),
            ("Calculate the centripetal force on the object.", 6, 4, "6a"),
            ("Explain how an electric field is created between two plates.", 5, 3, "7a"),
            ("Describe the process of nuclear fission.", 6, 3, "8a"),
            ("Explain the concept of specific heat capacity.", 5, 4, "9a"),
        ],
    },
    # Session 5: Edexcel 9PH0, 6 questions, ~75%
    {
        "board": "Edexcel", "spec": "9PH0",
        "questions": [
            ("Explain the importance of SI units in physics.", 4, 3, "1a"),
            ("Calculate the kinetic energy of the moving object.", 5, 4, "2c"),
            ("Determine the wavelength of the standing wave.", 6, 5, "5b"),
            ("Calculate the gravitational field strength at a distance.", 5, 4, "12a"),
            ("Describe the evidence for the expanding universe.", 6, 4, "10a"),
            ("Explain the properties of alpha, beta and gamma radiation.", 6, 5, "11a"),
        ],
    },
    # Session 6: OCR H240, 5 questions, NOT MARKED
    {
        "board": "OCR", "spec": "H240",
        "questions": [
            ("Prove that the sum of two odd numbers is even.", 4, None, "1a"),
            ("Factorise x^2 + 5x + 6.", 3, None, "2d"),
            ("Find the binomial expansion of (1 + x)^5.", 5, None, "4b"),
            ("Find dy/dx for y = sin(x)cos(x).", 4, None, "7b"),
            ("Find the area under the curve y = x^2 from 0 to 3.", 5, None, "8b"),
        ],
    },
]


def clean():
    """Delete all existing data for the test guest user."""
    with Session(ENGINE) as db:
        sessions = db.exec(
            select(DBSess).where(DBSess.user_id == GUEST_ID)
        ).all()

        if not sessions:
            return 0

        session_ids = [s.session_id for s in sessions]

        questions = db.exec(
            select(DBQuestion).where(DBQuestion.session_id.in_(session_ids))
        ).all()
        question_ids = [q.id for q in questions]

        if question_ids:
            preds = db.exec(
                select(DBPrediction).where(DBPrediction.question_id.in_(question_ids))
            ).all()
            for p in preds:
                db.delete(p)

            marks = db.exec(
                select(QuestionMark).where(QuestionMark.question_id.in_(question_ids))
            ).all()
            for m in marks:
                db.delete(m)

            for q in questions:
                db.delete(q)

        for s in sessions:
            db.delete(s)

        db.commit()
        return len(sessions)


def seed():
    base_time = datetime.utcnow() - timedelta(days=30)

    with Session(ENGINE) as db:
        for i, sess_def in enumerate(SESSIONS):
            session_id = str(uuid.uuid4())
            board = sess_def["board"]
            spec = sess_def["spec"]

            has_marks = any(q[2] is not None for q in sess_def["questions"])

            db_session = DBSess(
                session_id=session_id,
                user_id=GUEST_ID,
                is_guest=True,
                exam_board=board,
                subject=spec,
                created_at=base_time + timedelta(days=i * 5),
                status="marked" if has_marks else "not_marked",
            )
            db.add(db_session)

            total_available = 0
            total_achieved = 0

            for q_idx, (text, marks_avail, marks_ach, subtopic_id) in enumerate(sess_def["questions"]):
                db_question = DBQuestion(
                    session_id=session_id,
                    question_number=str(q_idx + 1),
                    question_text=text,
                    status="marked" if marks_ach is not None else "not_marked",
                )
                db.add(db_question)
                db.flush()

                db_mark = QuestionMark(
                    question_id=db_question.id,
                    marks_available=marks_avail,
                    marks_achieved=marks_ach,
                )
                db.add(db_mark)

                total_available += marks_avail
                if marks_ach is not None:
                    total_achieved += marks_ach

                info = lookup(board, spec, subtopic_id)
                db_pred = DBPrediction(
                    question_id=db_question.id,
                    rank=1,
                    strand=info["strand"],
                    topic=info["topic"],
                    subtopic=info["subtopic"],
                    spec_sub_section=info["spec_sub_section"],
                    similarity_score=0.85,
                    description=info["description"],
                )
                db.add(db_pred)

            db_session.total_marks_available = total_available
            if has_marks:
                db_session.total_marks_achieved = total_achieved
            db.add(db_session)

            pct = f" ({round(total_achieved / total_available * 100)}%)" if has_marks else " (unmarked)"
            print(f"  Session {i+1}: {board} {spec} — {len(sess_def['questions'])} questions{pct}  [{session_id}]")

        db.commit()


if __name__ == "__main__":
    deleted = clean()
    if deleted:
        print(f"Cleaned {deleted} existing session(s) for '{GUEST_ID}'")

    print(f"Seeding sessions for guest '{GUEST_ID}'...")
    seed()
    print("Done!")
