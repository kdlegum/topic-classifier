async function getSessionID(question_text){
    const response = await fetch('http://127.0.0.1:8000/classify/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ question_text: [question_text], ExamBoard: 'OCR', SpecCode: 'H240'})
    });
    const data = await response.json();
    //console.log(data.session_id);
    return data.session_id;
}

async function getClassificatinonResults(session_id){
    const response = await fetch(`http://127.0.0.1:8000/session/${session_id}/`);
    const data = await response.json();
    return data;
}

document.getElementById('submit_question_button').addEventListener('click', async function() {
    var questionText = document.getElementById('question_input').value;
    var sessionID = await getSessionID(questionText);
    //console.log(sessionID);
    var results = await getClassificatinonResults(sessionID);

    


    results = results.questions[0].predictions;
    //console.log(results[0]);
    var responseText = JSON.stringify(results, null, 2);
    document.getElementById('response_paragraph').innerText = responseText;
    //document.getElementById('description_paragraph').innerText = results.description;

});