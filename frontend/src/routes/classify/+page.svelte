<script lang="ts">
	import { goto } from '$app/navigation';
	import { classifyQuestions, uploadPdf, getPdfStatus } from '$lib/api';

	let specCode = $state('None');
	let questions = $state(['']);
	let isSubmitting = $state(false);
	let isUploading = $state(false);
	let pdfStatus = $state('');

	let fileInput: HTMLInputElement;

	function addQuestion() {
		questions = [...questions, ''];
	}

	async function handleSubmit() {
		const filled = questions.map((q) => q.trim()).filter((q) => q !== '');

		if (filled.length === 0) {
			alert('Please enter at least one question.');
			return;
		}

		if (specCode === 'None') {
			alert('Please choose the specification.');
			return;
		}

		isSubmitting = true;

		try {
			const data = await classifyQuestions(filled, specCode);
			goto(`/mark_session/${data.session_id}`);
		} catch (error) {
			console.error('Error submitting questions:', error);
			alert('There was an error sending your questions. See console for details.');
		} finally {
			isSubmitting = false;
		}
	}

	async function handlePdfUpload() {
		const file = fileInput?.files?.[0];

		if (!file) {
			alert('Please select a PDF file first.');
			return;
		}

		if (file.type !== 'application/pdf') {
			alert('Only PDF files are allowed.');
			return;
		}

		if (specCode === 'None') {
			alert('Please choose the specification.');
			return;
		}

		isUploading = true;
		pdfStatus = 'Uploading...';

		try {
			const data = await uploadPdf(file, specCode);
			pollJobStatus(data.job_id);
		} catch (error) {
			console.error('Error uploading PDF:', error);
			alert('Failed to upload PDF.');
			isUploading = false;
			pdfStatus = '';
		}
	}

	function pollJobStatus(jobId: string) {
		const interval = setInterval(async () => {
			try {
				const data = await getPdfStatus(jobId);
				pdfStatus = `Processing... ${data.status}`;

				if (data.status === 'Done') {
					clearInterval(interval);
					isUploading = false;

					if (!data.session_id) {
						throw new Error('Job completed but no session_id returned');
					}

					goto(`/mark_session/${data.session_id}`);
				}

				if (data.status === 'failed') {
					clearInterval(interval);
					isUploading = false;
					alert('PDF processing failed.');
					pdfStatus = 'Processing failed.';
				}
			} catch (err) {
				console.error(err);
				clearInterval(interval);
				isUploading = false;
				alert('Error checking PDF status.');
				pdfStatus = '';
			}
		}, 1000);
	}
</script>

<svelte:head>
	<title>Classify - Topic Tracker</title>
</svelte:head>

<main class="page-content">
	<h1>Exam Question Classifier</h1>
	<p>Paste your exam questions below or upload an empty question paper and get a topic breakdown.</p>

	<!-- Specification selection -->
	<div class="section">
		<label for="specification">Specification</label>
		<select id="specification" bind:value={specCode}>
			<option value="None">---Choose a Specification---</option>
			<option value="H240">OCR A Level Mathematics (H240)</option>
			<option value="9PH0">Edexcel A Level Physics (9PH0)</option>
			<option value="H645">OCR MEI B A Level Further Mathematics (H645) (All Options)</option>
		</select>
	</div>

	<!-- Questions -->
	<div class="section">
		<label for="question-text-field">Questions</label>

		{#each questions as question, i}
			<div class="question">
				<input
					id="question-text-field"
					placeholder="Enter question text here..."
					bind:value={questions[i]}
				/>
			</div>
		{/each}

		<button type="button" class="add-question" onclick={addQuestion}>
			+ Add another question
		</button>

		<button type="button" class="submit" onclick={handleSubmit} disabled={isSubmitting}>
			{isSubmitting ? 'Classifying...' : 'Submit all questions'}
		</button>
	</div>

	<!-- PDF Upload -->
	<div class="section">
		<label for="pdf-upload">Or upload an empty question paper (PDF)</label>
		<input type="file" id="pdf-upload" accept="application/pdf" bind:this={fileInput} />
		<button type="button" onclick={handlePdfUpload} disabled={isUploading}>
			Upload PDF
		</button>
		{#if pdfStatus}
			<div class="pdf-status">{pdfStatus}</div>
		{/if}
	</div>
</main>
