<script lang="ts">
	import { onMount } from 'svelte';
	import { fly, fade, slide } from 'svelte/transition';
	import { getRevisionPool, recordRevisionAttempt, downloadSessionPdf, getSpecs } from '$lib/api';
	import type { RevisionQuestion, SpecInfo } from '$lib/api';
	import MathText from '$lib/components/MathText.svelte';
	import PdfQuestionView from '$lib/components/PdfQuestionView.svelte';
	import { celebrateFullMarks } from '$lib/celebrations';

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
	let deleting: boolean = $state(false);
	let questionKey: number = $state(0);

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
		questionKey++;

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
				celebrateFullMarks();
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

	async function handleDeleteFromPool() {
		if (!currentQuestion || deleting) return;
		deleting = true;
		try {
			await recordRevisionAttempt(currentQuestion.question_id, currentQuestion.marks_available);
			totalCount = Math.max(0, totalCount - 1);
			pickNext();
		} catch (e) {
			console.error('Failed to remove from pool:', e);
		} finally {
			deleting = false;
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
		return 'Unclassified';
	}

	onMount(() => {
		fetchPool();
	});
</script>

<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.22/dist/katex.min.css" />

<div class="revision-page">
	{#if loading}
		<div class="centered">
			<div class="spinner"></div>
			<p class="muted">Loading revision pool...</p>
		</div>
	{:else if !currentQuestion}
		<div class="centered" in:fade={{ duration: 200 }}>
			<div class="empty-icon">&#10003;</div>
			<h2 class="empty-title">No questions available</h2>
			<p class="muted">Questions appear here when you've scored below full marks on a session. Mark some exam sessions to build your revision pool.</p>
		</div>
	{:else}
	<!-- TODO: Take content out especially for mobile since info like cards left shouldn't be part of the revision card. -->
		<div class = "transition-container">
			{#key questionKey}
				<div class="revision-content" in:fly={{ x: 300, duration: 300, delay: 50 }} out:fly={{ x: -300, duration: 300 }}>
					<div class="top-bar">
						<div class="top-bar-left">
							<span class="spec-badge">{specDisplayName(currentQuestion.spec_code)}</span>
							<span class="meta">Q{currentQuestion.question_number}</span>
							<span class="meta-dot">·</span>
							<span class="meta">{currentQuestion.marks_available} mark{currentQuestion.marks_available !== 1 ? 's' : ''}</span>
						</div>
						<div class="top-bar-right">
							<select class="spec-filter" value={specFilter} onchange={handleFilterChange}>
								<option value="">All specs</option>
								{#each specCodes as code}
									<option value={code}>{specDisplayName(code)}</option>
								{/each}
							</select>
							<span class="pool-count">{totalCount} left</span>
						</div>
					</div>

					<div class="question-body">
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

					<div class="bottom-controls">
						<div class="actions-row">
							{#if currentQuestion.has_pdf && currentQuestion.pdf_location}
								<button class="action-btn" onclick={() => (showPdf = !showPdf)}>
									{showPdf ? 'View text' : 'View full question'}
								</button>
							{/if}
							<button class="action-btn" onclick={handleDownloadPdf} disabled={downloading || !currentQuestion.has_pdf}>
								{downloading ? 'Downloading...' : 'Download PDF'}
							</button>
							<button class="action-btn remove" onclick={handleDeleteFromPool} disabled={deleting || submitted}>
								{deleting ? 'Removing...' : 'Remove from pool'}
							</button>
						</div>

						{#if !submitted}
							<div class = "slide-wrapper" out:slide={{ duration: 200, axis: 'y' }}>
								<div class="submit-row">
									<div class="marks-group">
										<input
											type="number"
											class="marks-input"
											bind:value={marksInput}
											min="0"
											max={currentQuestion.marks_available}
										/>
										<span class="marks-divider">/ {currentQuestion.marks_available} marks</span>
									</div>
									<div class="submit-actions">
										<button class="action-btn" onclick={pickNext}>Skip</button>
										<button class="primary-btn" onclick={handleSubmit} disabled={submitting}>
											{submitting ? 'Submitting...' : 'Submit'}
										</button>
									</div>
								</div>
							</div>
						{:else if submitResult}
							<div
								class="result-section"
								class:full-marks={submitResult.is_full_marks}
								class:partial={!submitResult.is_full_marks}
								in:slide={{ duration: 300, axis: 'y' }}
							>
								<div class="result-banner">
									{#if submitResult.is_full_marks}
										<span class="result-icon">&#10003;</span>
										<span>Full marks — removed from pool</span>
									{:else}
										<span class="result-icon">&#8635;</span>
										<span>Stays in pool for next time</span>
									{/if}
								</div>

								<div class="result-details">
									<div class="result-row">
										<span class="detail-label">Topic</span>
										<span class="detail-value">{topicDisplay(currentQuestion)}</span>
									</div>
									<div class="result-row">
										<span class="detail-label">Original</span>
										<span class="detail-value">{currentQuestion.original_marks_achieved}/{currentQuestion.marks_available}</span>
									</div>
									<div class="result-row">
										<span class="detail-label">This attempt</span>
										<span class="detail-value">{marksInput}/{currentQuestion.marks_available}</span>
									</div>
								</div>

								<button class="primary-btn next-btn" onclick={pickNext}>Next Question</button>
							</div>
						{/if}
					</div>

				</div>
			{/key}
		</div>
	{/if}
</div>

<style>
	.transition-container {
		display: grid;
		grid-template-columns: 1fr;
		grid-template-rows: 1fr;
		width: 100%;
		align-items: start;
	}

	.revision-page {
		max-width: 720px;
		margin: 0 auto;
		padding: 80px 20px 40px;
		min-height: calc(100vh - 80px);
		display: flex;
		flex-direction: column;
		justify-content: flex-start;
	}

	/* Centered states */
	.centered {
		text-align: center;
		padding: 40px 24px;
	}

	.centered .muted {
		margin: 8px auto 0;
		font-size: 0.92rem;
		max-width: 400px;
		line-height: 1.5;
		color: var(--color-text-muted);
	}

	.spinner {
		width: 28px;
		height: 28px;
		border: 3px solid var(--color-border);
		border-top-color: var(--color-primary);
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
		background: var(--color-success-bg);
		color: var(--color-success);
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 1.4rem;
		margin: 0 auto 16px;
	}

	.empty-title {
		font-size: 1.1rem;
		font-weight: 700;
		color: var(--color-text);
		margin: 0 0 6px;
	}

	/* Main content wrapper */
	.revision-content {
		display: flex;
		flex-direction: column;
		background: var(--color-surface);
		border-radius: var(--radius-lg);
		padding: 24px 28px;
		border: 1.5px solid var(--color-border);
		box-shadow: var(--shadow-md);

		grid-column: 1;
		grid-row: 1;
		width: 100%;
		backface-visibility: hidden;
	}

	/* Top bar */
	.top-bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding-bottom: 16px;
		border-bottom: 1px solid var(--color-border);
		flex-wrap: wrap;
		gap: 8px;
	}

	.top-bar-left {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.top-bar-right {
		display: flex;
		align-items: center;
		gap: 10px;
	}

	.spec-badge {
		font-size: 0.78rem;
		background: var(--color-primary-light);
		color: #0F766E;
		padding: 2px 8px;
		border-radius: 3px;
		font-weight: 600;
	}

	.meta {
		font-size: 0.85rem;
		color: var(--color-text-secondary);
	}

	.meta-dot {
		color: var(--color-border);
		font-size: 0.85rem;
	}

	.spec-filter {
		padding: 4px 8px;
		border: 1.5px solid var(--color-border);
		border-radius: var(--radius-sm);
		font-size: 0.82rem;
		background: var(--color-surface);
		color: var(--color-text);
		font-family: var(--font-body);
	}

	.pool-count {
		font-size: 0.8rem;
		color: var(--color-text-muted);
		white-space: nowrap;
	}

	/* Question body */
	.question-body {
		padding: 32px 4px;
		min-height: 120px;
	}

	.question-text {
		line-height: 1.7;
		color: var(--color-text);
		font-size: 1rem;
	}

	/* Bottom controls */
	.bottom-controls {
		border-top: 1px solid var(--color-border);
	}

	.actions-row {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 12px 0;
		flex-wrap: wrap;
	}

	.action-btn {
		padding: 6px 12px;
		border-radius: var(--radius-sm);
		font-size: 0.82rem;
		font-weight: 600;
		cursor: pointer;
		border: 1.5px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text-secondary);
		transition: background var(--transition-fast), color var(--transition-fast), transform var(--transition-fast);
		white-space: nowrap;
		font-family: var(--font-body);
	}

	.action-btn:hover:not(:disabled) {
		background: var(--color-surface-alt);
		color: var(--color-text);
	}

	.action-btn:active:not(:disabled) {
		transform: scale(0.97);
	}

	.action-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}

	.action-btn.remove {
		border-color: transparent;
		background: transparent;
		color: var(--color-text-muted);
		margin-left: auto;
	}

	.action-btn.remove:hover:not(:disabled) {
		color: var(--color-error);
		background: var(--color-error-bg);
	}

	/* Submit row */
	.submit-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 12px 0;
		border-top: 1px solid var(--color-border);
		flex-wrap: wrap;
		gap: 10px;
	}

	.marks-group {
		display: flex;
		align-items: center;
		gap: 5px;
	}

	.marks-input {
		width: 56px;
		padding: 10px 8px;
		border: 1.5px solid var(--color-border);
		border-radius: var(--radius-sm);
		font-size: 1.1rem;
		text-align: center;
		font-weight: 700;
		font-family: var(--font-body);
		transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
	}

	.marks-input:focus {
		outline: none;
		border-color: var(--color-primary);
		box-shadow: 0 0 0 3px var(--color-primary-glow);
	}

	.marks-divider {
		font-size: 0.95rem;
		color: var(--color-text-muted);
	}

	.submit-actions {
		display: flex;
		align-items: center;
		gap: 10px;
	}

	.submit-actions .action-btn {
		padding: 10px 16px;
		font-size: 0.9rem;
		border-radius: var(--radius-sm);
	}

	.primary-btn {
		padding: 10px 24px;
		border-radius: var(--radius-sm);
		font-size: 0.92rem;
		font-weight: 700;
		cursor: pointer;
		border: none;
		background: var(--color-primary);
		color: #fff;
		transition: background var(--transition-fast), transform var(--transition-fast);
		white-space: nowrap;
		font-family: var(--font-body);
	}

	.primary-btn:hover:not(:disabled) {
		background: var(--color-primary-hover);
	}

	.primary-btn:active:not(:disabled) {
		transform: scale(0.97);
	}

	.primary-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	/* Result */
	.result-section {
		padding: 12px 0 4px;
		border-top: 1px solid var(--color-border);
	}

	.result-banner {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 10px 14px;
		border-radius: var(--radius-md);
		font-size: 0.88rem;
		font-weight: 600;
		margin-bottom: 12px;
	}

	.full-marks .result-banner {
		background: var(--color-success-bg);
		color: var(--color-success);
	}

	.partial .result-banner {
		background: var(--color-warning-bg);
		color: #D97706;
	}

	.result-icon {
		font-size: 1rem;
	}

	.result-details {
		display: flex;
		flex-direction: column;
		gap: 6px;
		margin-bottom: 14px;
	}

	.result-row {
		display: flex;
		justify-content: space-between;
		font-size: 0.85rem;
	}

	.detail-label {
		color: var(--color-text-muted);
	}

	.detail-value {
		color: var(--color-text);
		font-weight: 600;
		text-align: right;
		max-width: 60%;
	}

	.next-btn {
		width: 100%;
		padding: 10px;
	}

	/* Mobile */
	@media (max-width: 500px) {
		.revision-page {
			padding: 12px 10px;
		}

		.revision-content {
			padding: 16px 16px;
		}

		.question-body {
			padding: 24px 2px;
		}

		.actions-row {
			gap: 6px;
		}

		.action-btn.remove {
			margin-left: 0;
		}

		.submit-row {
			flex-direction: column;
			align-items: stretch;
		}

		.marks-group {
			justify-content: center;
		}

		.submit-actions {
			display: flex;
		}

		.submit-actions .action-btn,
		.submit-actions .primary-btn {
			flex: 1;
			text-align: center;
		}
	}
</style>
