<script lang="ts">
	import { onMount } from 'svelte';
	import { getRevisionPool, recordRevisionAttempt, downloadSessionPdf, getSpecs } from '$lib/api';
	import type { RevisionQuestion, SpecInfo } from '$lib/api';
	import MathText from '$lib/components/MathText.svelte';
	import PdfQuestionView from '$lib/components/PdfQuestionView.svelte';

	let specFilter: string = $state('');
	let questionBatch: RevisionQuestion[] = $state([]);
	let currentQuestion: RevisionQuestion | null = $state(null);
	let totalCount: number = $state(0);
	let specCodes: string[] = $state([]);
	let specs: SpecInfo[] = $state([]);
	let loading: boolean = $state(true);
	let marksInput: number = $state(0);
	let submitted: boolean = $state(false);
	let submitResult: { success: boolean; is_full_marks: boolean } | null = $state(null);
	let showPdf: boolean = $state(false);
	let fetching: boolean = $state(false);
	let downloading: boolean = $state(false);
	let submitting: boolean = $state(false);

	function specDisplayName(code: string): string {
		const spec = specs.find((s) => s.spec_code === code);
		if (spec) return `${spec.exam_board} ${spec.subject}`;
		return code;
	}

	function pickNext() {
		submitted = false;
		submitResult = null;
		showPdf = false;
		marksInput = 0;

		if (questionBatch.length === 0) {
			currentQuestion = null;
			return;
		}

		const idx = Math.floor(Math.random() * questionBatch.length);
		currentQuestion = questionBatch.splice(idx, 1)[0];

		if (questionBatch.length < 3 && !fetching) {
			refillBatch();
		}
	}

	async function refillBatch() {
		fetching = true;
		try {
			const pool = await getRevisionPool(specFilter || undefined, 20);
			const existingIds = new Set(questionBatch.map((q) => q.question_id));
			if (currentQuestion) existingIds.add(currentQuestion.question_id);
			const newQuestions = pool.questions.filter((q) => !existingIds.has(q.question_id));
			questionBatch = [...questionBatch, ...newQuestions];
		} catch (e) {
			console.error('Failed to refill batch:', e);
		} finally {
			fetching = false;
		}
	}

	async function fetchPool(filterCode?: string) {
		loading = true;
		try {
			const [pool, specList] = await Promise.all([
				getRevisionPool(filterCode || undefined, 20),
				specs.length === 0 ? getSpecs() : Promise.resolve(specs)
			]);
			if (specs.length === 0) specs = specList;
			questionBatch = pool.questions;
			totalCount = pool.total_count;
			specCodes = pool.spec_codes;
			pickNext();
		} catch (e) {
			console.error('Failed to fetch revision pool:', e);
			questionBatch = [];
			currentQuestion = null;
			totalCount = 0;
		} finally {
			loading = false;
		}
	}

	async function handleSubmit() {
		if (!currentQuestion || submitting) return;
		submitting = true;
		try {
			const result = await recordRevisionAttempt(currentQuestion.question_id, marksInput);
			submitResult = result;
			submitted = true;
			if (result.is_full_marks) {
				totalCount = Math.max(0, totalCount - 1);
			}
		} catch (e) {
			console.error('Failed to record attempt:', e);
		} finally {
			submitting = false;
		}
	}

	async function handleDownloadPdf() {
		if (!currentQuestion || downloading) return;
		downloading = true;
		try {
			const blob = await downloadSessionPdf(currentQuestion.session_id);
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = `${currentQuestion.exam_board}_${currentQuestion.spec_code}.pdf`;
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(url);
		} catch (e) {
			console.error('Failed to download PDF:', e);
		} finally {
			downloading = false;
		}
	}

	function handleFilterChange(e: Event) {
		const value = (e.target as HTMLSelectElement).value;
		specFilter = value;
		questionBatch = [];
		currentQuestion = null;
		fetchPool(value);
	}

	function topicDisplay(q: RevisionQuestion): string {
		if (q.user_corrections.length > 0) {
			return q.user_corrections.map((c) => `${c.spec_sub_section} ${c.subtopic}`).join(', ');
		}
		if (q.predictions.length > 0) {
			const p = q.predictions[0];
			return `${p.spec_sub_section} ${p.subtopic}`;
		}
		return 'No topic data';
	}

	onMount(() => {
		fetchPool();
	});
</script>

<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.22/dist/katex.min.css" />

<div class="revision-page">
	<div class="revision-header">
		<h1>Revision</h1>
		<div class="controls">
			<select class="spec-filter" value={specFilter} onchange={handleFilterChange}>
				<option value="">All specifications</option>
				{#each specCodes as code}
					<option value={code}>{specDisplayName(code)}</option>
				{/each}
			</select>
			<span class="pool-badge">{totalCount} question{totalCount !== 1 ? 's' : ''} in pool</span>
		</div>
	</div>

	{#if loading}
		<div class="state-card">
			<div class="spinner"></div>
			<p>Loading revision pool...</p>
		</div>
	{:else if !currentQuestion}
		<div class="state-card empty">
			<div class="empty-icon">&#10003;</div>
			<h2>No questions available for revision</h2>
			<p>Questions appear here when you've marked a session and scored below full marks. Complete and mark some exam sessions to build your revision pool.</p>
		</div>
	{:else}
		<div class="question-card">
			<div class="card-header">
				<span class="question-number">Q{currentQuestion.question_number}</span>
				<span class="spec-badge">{specDisplayName(currentQuestion.spec_code)}</span>
				<span class="marks-label">{currentQuestion.marks_available} mark{currentQuestion.marks_available !== 1 ? 's' : ''}</span>
			</div>

			<div class="card-body">
				{#if showPdf && currentQuestion.pdf_location}
					<PdfQuestionView
						sessionId={currentQuestion.session_id}
						pdfLocation={currentQuestion.pdf_location}
					/>
				{:else}
					<div class="question-text">
						<MathText text={currentQuestion.question_text} />
					</div>
				{/if}
			</div>

			<div class="card-actions">
				{#if currentQuestion.has_pdf && currentQuestion.pdf_location}
					<button class="btn btn-outline" onclick={() => (showPdf = !showPdf)}>
						{showPdf ? 'View Text' : 'View PDF'}
					</button>
				{/if}
				<button class="btn btn-outline" onclick={handleDownloadPdf} disabled={downloading || !currentQuestion.has_pdf}>
					{downloading ? 'Downloading...' : 'Download PDF'}
				</button>
			</div>

			{#if !submitted}
				<div class="marking-section">
					<label class="marks-input-label">
						Marks achieved
						<div class="marks-input-row">
							<input
								type="number"
								class="marks-input"
								bind:value={marksInput}
								min="0"
								max={currentQuestion.marks_available}
							/>
							<span class="marks-total">/ {currentQuestion.marks_available}</span>
						</div>
					</label>
					<button class="btn btn-primary" onclick={handleSubmit} disabled={submitting}>
						{submitting ? 'Submitting...' : 'Submit Mark'}
					</button>
				</div>
			{:else if submitResult}
				<div class="result-section" class:full-marks={submitResult.is_full_marks} class:partial={!submitResult.is_full_marks}>
					<div class="result-banner">
						{#if submitResult.is_full_marks}
							<span class="result-icon good">&#10003;</span>
							<span>Full marks — removed from revision pool</span>
						{:else}
							<span class="result-icon retry">&#8635;</span>
							<span>Stays in revision pool for next time</span>
						{/if}
					</div>

					<div class="result-details">
						<div class="result-row">
							<span class="detail-label">Topic</span>
							<span class="detail-value">{topicDisplay(currentQuestion)}</span>
						</div>
						<div class="result-row">
							<span class="detail-label">Original score</span>
							<span class="detail-value">{currentQuestion.original_marks_achieved} / {currentQuestion.marks_available}</span>
						</div>
						<div class="result-row">
							<span class="detail-label">This attempt</span>
							<span class="detail-value">{marksInput} / {currentQuestion.marks_available}</span>
						</div>
					</div>

					<button class="btn btn-primary" onclick={pickNext}>Next Question</button>
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.revision-page {
		max-width: 760px;
		margin: 0 auto;
		padding: 32px 20px;
	}

	.revision-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 24px;
		flex-wrap: wrap;
		gap: 12px;
	}

	.revision-header h1 {
		margin: 0;
		font-size: 1.5rem;
		font-weight: 600;
		color: #1a1a1a;
	}

	.controls {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.spec-filter {
		padding: 6px 10px;
		border: 1px solid #d0d0d0;
		border-radius: 6px;
		font-size: 0.9rem;
		background: #fff;
		color: #333;
	}

	.pool-badge {
		font-size: 0.85rem;
		color: #555;
		background: #f0f0f0;
		padding: 4px 10px;
		border-radius: 12px;
		white-space: nowrap;
	}

	/* State cards */
	.state-card {
		text-align: center;
		padding: 60px 24px;
		color: #666;
	}

	.state-card p {
		margin: 8px 0 0;
		font-size: 0.95rem;
		max-width: 420px;
		margin-left: auto;
		margin-right: auto;
		line-height: 1.5;
	}

	.spinner {
		width: 28px;
		height: 28px;
		border: 3px solid #e0e0e0;
		border-top-color: #0077cc;
		border-radius: 50%;
		animation: spin 0.7s linear infinite;
		margin: 0 auto 12px;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	.empty-icon {
		width: 48px;
		height: 48px;
		border-radius: 50%;
		background: #e8f5e9;
		color: #2e7d32;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 1.4rem;
		margin: 0 auto 16px;
	}

	.empty h2 {
		font-size: 1.15rem;
		font-weight: 600;
		color: #333;
		margin: 0 0 6px;
	}

	/* Question card */
	.question-card {
		border: 1px solid #e0e0e0;
		border-radius: 10px;
		background: #fff;
		overflow: hidden;
	}

	.card-header {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 14px 20px;
		border-bottom: 1px solid #f0f0f0;
		background: #fafafa;
	}

	.question-number {
		font-weight: 700;
		font-size: 1rem;
		color: #1a1a1a;
	}

	.spec-badge {
		font-size: 0.8rem;
		background: #e8f0fe;
		color: #1a56db;
		padding: 2px 8px;
		border-radius: 4px;
		font-weight: 500;
	}

	.marks-label {
		margin-left: auto;
		font-size: 0.85rem;
		color: #777;
	}

	.card-body {
		padding: 20px;
		min-height: 80px;
	}

	.question-text {
		line-height: 1.6;
		color: #222;
	}

	.card-actions {
		display: flex;
		gap: 8px;
		padding: 0 20px 16px;
	}

	/* Buttons */
	.btn {
		padding: 8px 16px;
		border-radius: 6px;
		font-size: 0.9rem;
		font-weight: 500;
		cursor: pointer;
		border: none;
		transition: background 0.15s, opacity 0.15s;
	}

	.btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.btn-primary {
		background: #0077cc;
		color: #fff;
	}

	.btn-primary:hover:not(:disabled) {
		background: #005fa3;
	}

	.btn-outline {
		background: #fff;
		color: #555;
		border: 1px solid #d0d0d0;
	}

	.btn-outline:hover:not(:disabled) {
		background: #f5f5f5;
	}

	/* Marking */
	.marking-section {
		display: flex;
		align-items: flex-end;
		gap: 12px;
		padding: 16px 20px;
		border-top: 1px solid #f0f0f0;
		background: #fafafa;
	}

	.marks-input-label {
		font-size: 0.85rem;
		font-weight: 500;
		color: #555;
	}

	.marks-input-row {
		display: flex;
		align-items: center;
		gap: 6px;
		margin-top: 4px;
	}

	.marks-input {
		width: 60px;
		padding: 6px 8px;
		border: 1px solid #d0d0d0;
		border-radius: 6px;
		font-size: 1rem;
		text-align: center;
	}

	.marks-total {
		font-size: 0.95rem;
		color: #777;
	}

	/* Result */
	.result-section {
		padding: 16px 20px 20px;
		border-top: 1px solid #f0f0f0;
	}

	.result-banner {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 10px 14px;
		border-radius: 6px;
		font-size: 0.9rem;
		font-weight: 500;
		margin-bottom: 16px;
	}

	.full-marks .result-banner {
		background: #e8f5e9;
		color: #2e7d32;
	}

	.partial .result-banner {
		background: #fff8e1;
		color: #f57f17;
	}

	.result-icon {
		font-size: 1.1rem;
	}

	.result-details {
		display: flex;
		flex-direction: column;
		gap: 8px;
		margin-bottom: 16px;
	}

	.result-row {
		display: flex;
		justify-content: space-between;
		font-size: 0.9rem;
	}

	.detail-label {
		color: #777;
	}

	.detail-value {
		color: #333;
		font-weight: 500;
		text-align: right;
		max-width: 60%;
	}
</style>
