//Adding question fields functionality

document.addEventListener('DOMContentLoaded', () => {
    const addQuestionButton = document.querySelector('.add-question');
    const questionsContainer = document.getElementById('questions-container');
    const submitButton = document.querySelector('.submit');

    if (addQuestionButton && questionsContainer){
        addQuestionButton.addEventListener('click', () => {
        addNewQuestionField();
    });
    }

    if (submitButton){
        submitButton.addEventListener('click', () => {
            handleSubmit();
        });
    }
});

function addNewQuestionField() {
    const questionsContainer = document.getElementById('questions-container');
    const newQuestionDiv = document.createElement('div');
    newQuestionDiv.classList.add('question');

    const textArea = document.createElement('textarea');
    textArea.placeholder = 'Enter your question here...';

    newQuestionDiv.appendChild(textArea);
    questionsContainer.appendChild(newQuestionDiv);

}

async function handleSubmit(){
    const textAreas = document.querySelectorAll('#questions-container textarea');
    var questions = [];
    textAreas.forEach((textarea) => {
        if (textarea.value.trim() !== ''){
            questions.push(textarea.value.trim());
        }
    });

    if (questions.length === 0) {
        alert("Please enter at least one question.");
        return;
    }
     
    const spec = document.getElementById('specification').value;

    //Submitting to backend
    try {
    const response = await fetch("/classify/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      specification: spec,
      questions: questions
    })
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const data = await response.json();
  console.log("Classification Results:", JSON.stringify(data));

  //Todo: Display the response

} 
catch (error) {
  console.error("Error submitting questions:", error);
  alert("There was an error sending your questions. See console for details.");
}
}





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

