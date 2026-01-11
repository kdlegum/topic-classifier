
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

def classify_questions(question_text):
    """
    Classify a list of questions to its best matching sub-topic.
    
    Args:
        question_text: An array of question strings
    
    Returns:
        List of best matching sub-topic names for each question

    """
    f = open("topics.json", "r", encoding="utf-8")
    topics = json.load(f)
    topicList = topics["Topics"]
    subTopicNames = []
    for t in topicList:
        for s in t["Sub_topics"]:
            subTopicNames.append(s["Sub_topic_name"])
    

    similarities_sub_topics = findSimilarity(question_text)
    best_sub_topic = np.argmax(similarities_sub_topics, axis=0)
    best_sub_topic_names = [subTopicNames[i] for i in best_sub_topic]

    return best_sub_topic_names

print(classify_questions(["Explain the connection between the expression in part bi and the binomial expansion of (0.7 + 0.3)^n for a specific value of n which should be stated.",
                          "The masses, M grams, of bags of flour are modelled by the distribution N(1002, 2.25). Find P(1000 < M < 1005)."]))