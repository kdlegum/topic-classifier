//Adding question fields functionality

document.addEventListener('DOMContentLoaded', () => {
    const addQuestionButton = document.querySelector('.add-question');
    const questionsContainer = document.getElementById('questions-container');
    const submitButton = document.querySelector('.submit');
    const uploadButton = document.getElementById("upload-pdf");

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

    if (uploadButton){
        uploadButton.addEventListener("click", () => {
            handleUpload();
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
    const response = await fetch("http://localhost:8000/classify", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
    question_text: questions,
    SpecCode: spec,
    })
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const data = await response.json();
  console.log("Classification Results:", JSON.stringify(data));
  displayResults(data);
  //Todo: Display the response

} 
catch (error) {
  console.error("Error submitting questions:", error);
  alert("There was an error sending your questions. See console for details.");
}
}

async function handleUpload() {
    const fileInput = document.getElementById("pdf-upload");
    const file = fileInput.files[0];

    if (!file) {
        alert("Please select a PDF file first.");
        return;
    }

    if (file.type !== "application/pdf") {
        alert("Only PDF files are allowed.");
        return;
    }

    const formData = new FormData();
    formData.append("file", file);
    const SpecCode = document.getElementById('specification').value;

    
    try {
        const response = await fetch(`http://localhost:8000/upload-pdf/${SpecCode}`, {
            method: "POST",
            body: formData
        });

        if (!response.ok) {
            throw new Error(`Upload failed: ${response.status}`);
        }

        const data = await response.json();
        console.log("Upload success:", data)
        pollJobStatus(data.job_id)

    } catch (error) {
        console.error("Error uploading PDF:", error);
        alert("Failed to upload PDF.");
    }
}




function displayResults(data) {
        const container = document.getElementById("results");
    container.innerHTML = "";

    data.questions.forEach(question => {
        const qDiv = document.createElement("div");
        qDiv.classList.add("question-block");

        const qHeader = document.createElement("h3");
        qHeader.textContent = `Question ${question.question_number}:`;
        qDiv.appendChild(qHeader);

        const qText = document.createElement("p");
        qText.textContent = `${question.question_text}`;
        qDiv.appendChild(qText);

        question.predictions.forEach(pred => {
            const wrapper = document.createElement("div");
            wrapper.classList.add("prediction");

            // Main line
            const mainLine = document.createElement("p");
            mainLine.innerHTML =
                `Rank ${pred.rank}: ${pred.strand} → ${pred.topic} → ` +
                `<span class="subtopic clickable">${pred.subtopic}</span> ` +
                `(Similarity score ${pred.similarity_score})`;
            wrapper.appendChild(mainLine);

            // Hidden description
            const desc = document.createElement("div");
            desc.classList.add("description");
            desc.textContent = pred.description;
            desc.style.display = "none";
            wrapper.appendChild(desc);

            // Toggle behaviour
            mainLine.querySelector(".subtopic").addEventListener("click", () => {
                desc.style.display = desc.style.display === "none" ? "block" : "none";
            });

            qDiv.appendChild(wrapper);
        });

        container.appendChild(qDiv);
    });
}

async function fetchSessionResults(sessionId) {
    try {
        const res = await fetch(`/session/${sessionId}`);
        if (!res.ok) throw new Error("Failed to fetch session results");

        const data = await res.json();

        // Hand off to your existing renderer
        displayResults(data);

    } catch (err) {
        console.error(err);
        alert("Error loading results.");
    }
}

async function pollJobStatus(jobId) {
    const intervalMs = 1000;

    const poller = setInterval(async () => {
        try {
            const res = await fetch(`/upload-pdf-status/${jobId}`);
            if (!res.ok) throw new Error("Status check failed");

            const data = await res.json();
            console.log("Job status:", data);

            if (data.status === "Done") {
                clearInterval(poller);

                if (!data.session_id) {
                    throw new Error("Job completed but no session_id returned");
                }

                // Now fetch the results
                await fetchSessionResults(data.session_id);
            }

            if (data.status === "failed") {
                clearInterval(poller);
                alert("PDF processing failed.");
            }

        } catch (err) {
            console.error(err);
            clearInterval(poller);
            alert("Error checking PDF status.");
        }
    }, intervalMs);
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

