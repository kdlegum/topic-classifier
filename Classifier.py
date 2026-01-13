
import numpy as np
import json
import requests
import time
"""
Input: Question Text + Topic List
Output: Predicted Topic for the question.
Model

"""
t0 = time.time()
def findSimilarity(questions):
    response = requests.post(f"http://127.0.0.1:8000/similarity/", json={"questions": questions})
    return response.json()

def classify_questions(question_text,SpecCode):
    response = requests.post(f"http://127.0.0.1:8000/classify/", json={"question_text": question_text, "SpecCode": SpecCode})
    return response.json()

def get_session(session_id):
    response = requests.get(f"http://127.0.0.1:8000/session/{session_id}/")
    return response.json()

questions = ["What is the derivative of sin(x)?",
             "Use the binomial theorem to expand (1 + x)^n for a specific value of n which should be stated."]
api_response = print(classify_questions(questions, "H240"))
