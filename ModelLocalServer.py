from fastapi import FastAPI, Query
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from typing import List
import numpy as np
import json
import time

app = FastAPI()

model = SentenceTransformer('all-MiniLM-L6-v2')

f = open("topics.json", "r", encoding="utf-8")
topics = json.load(f)
topicList = topics["Topics"]
subTopicNames = []
for t in topicList:
    for s in t["Sub_topics"]:
        subTopicNames.append(s["description"])
sub_topics_embed = model.encode(subTopicNames)


@app.get("/encode/")
def encode_text(text: str):
    return model.encode([text]).tolist()


@app.get("/similarity/")
def compute_similarity(q: List[str] = Query(...)):
    t0 = time.time()
    embed1 = model.encode(q)
    similarity = model.similarity(sub_topics_embed, embed1)
    print(f"Computed similarity for {len(q)} questions in {time.time() - t0:.2f} seconds")
    return similarity.tolist()
