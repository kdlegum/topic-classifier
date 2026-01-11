
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

def classify_questions(question_text, ExamBoard, SpecCode):
    response = requests.post(f"http://127.0.0.1:8000/classify/", json={"question_text": question_text, "ExamBoard": ExamBoard,"SpecCode": SpecCode})
    return response.json()

print(classify_questions(["Explain the connection between the expression in part bi and the binomial expansion of (0.7 + 0.3)^n for a specific value of n which should be stated.",
                          "The masses, M grams, of bags of flour are modelled by the distribution N(1002, 2.25). Find P(1000 < M < 1005)."],
                          "OCR", "H240"))