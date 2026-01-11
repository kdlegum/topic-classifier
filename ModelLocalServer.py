from fastapi import FastAPI, Query
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from typing import List
import numpy as np
import json
import time
import uuid
import datetime
from sessionDatabase import Session as DBSess, Question as DBQuestion, ClassificationResult as DBClassificationResult
from sqlmodel import Session, create_engine

engine = create_engine("sqlite:///exam_app.db")


app = FastAPI()

model = SentenceTransformer('all-MiniLM-L6-v2')

class similarityRequest(BaseModel):
    questions: List[str]

class classificationRequest(BaseModel):
    question_text: List[str]
    ExamBoard: str
    SpecCode: str

f = open("topics.json", "r", encoding="utf-8")
topics = json.load(f)
topicList = topics["Topics"]
subTopicNames = []
for t in topicList:
    for s in t["Sub_topics"]:
        subTopicNames.append(s["description"])
sub_topics_embed = model.encode(subTopicNames)

g = open("subtopics_index.json", "r", encoding="utf-8")
subtopics_index = json.load(g)

id = 0

@app.get("/encode/")
def encode_text(text: str):
    return model.encode([text]).tolist()


@app.post("/similarity/")
def compute_similarity(req: similarityRequest):
    t0 = time.time()
    embed1 = model.encode(req.questions)
    similarity = model.similarity(sub_topics_embed, embed1)
    print(f"Computed similarity for {len(req.questions)} questions in {time.time() - t0:.2f} seconds")
    return similarity.tolist()

@app.post("/classify/")
def classify_questions(req: classificationRequest):
    """
    Classify a list of questions to its best matching sub-topic.
    
    Args:
        question_text: An array of question strings
    
    Returns:
        An array of best matching sub-topic keys for each question for subtopics_index.json

    """
    f = open("topics.json", "r", encoding="utf-8")
    topics = json.load(f)
    topicList = topics["Topics"]
    subTopicIds = []
    for t in topicList:
        for s in t["Sub_topics"]:
            subTopicIds.append(s["subtopic_id"])
    

    similarities_sub_topics = compute_similarity(similarityRequest(questions=req.question_text))
    best_sub_topic = np.argmax(similarities_sub_topics, axis=0)
    confidences = np.max(similarities_sub_topics, axis=0)
    subTopicIds = [subTopicIds[i] for i in best_sub_topic]
    best_sub_topic_keys = [f"{req.ExamBoard}_{req.SpecCode}_{subTopicIds[i]}" for i in range(len(subTopicIds))]

    """
    Want to make a json structure like:
    {
  "session_id": "f3a2...",
  "results": [
    {
      "question_number": int,
      "strand": str,
      "topic": str,
      "subtopic": str,
      "spec_sub_section": str,
      "confidence": float
    }
  ]
}

    """
    resultList = []
    for i in range(len(best_sub_topic_keys)):
        j = best_sub_topic_keys[i]
        if j not in subtopics_index:
            j = None
        else:
            k = subtopics_index[j]
            resultList.append({
                "question_number": i+1,
                "strand": k["strand"],
                "topic": k["topic_name"],
                "subtopic": k["name"],
                "spec_sub_section": k["spec_sub_section"],
                "confidence": round(float(confidences[i]), 4)

            })  

    # Store in DB
    session_id = str(uuid.uuid4())

    with Session(engine) as session:

        # Add session to DB
        db_session = DBSess(
            session_id=session_id,
            exam_board=req.ExamBoard,
            subject=req.SpecCode
        )
        session.add(db_session)
        session.commit()
        session.refresh(db_session)


        # Add questions and classification results to DB
        for i in range(len(req.question_text)):
            db_question = DBQuestion(
                session_id=db_session.session_id,
                question_number=str(i+1),
                question_text=req.question_text[i]
            )
            session.add(db_question)
            session.commit()
            session.refresh(db_question)

            k = best_sub_topic_keys[i]
            if k not in subtopics_index:
                continue
            subtopic_info = subtopics_index[k]

            db_classification = DBClassificationResult(
                question_id=str(db_question.id),
                strand=subtopic_info["strand"],
                topic=subtopic_info["topic_name"],
                subtopic=subtopic_info["name"],
                spec_sub_section=subtopic_info["spec_sub_section"],
                confidence=float(round(float(confidences[i]), 4))
            )
            session.add(db_classification)
            session.commit()
    


    result = {
        "session_id": session_id,
        "results": resultList,
    }


    return result


