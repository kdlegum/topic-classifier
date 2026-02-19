<script lang="ts">
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import { fly, fade, slide } from 'svelte/transition';
	import { getSession, uploadAchievedMarks, updateQuestion, getTopicHierarchy, saveUserCorrections, downloadSessionPdf } from '$lib/api';
	import TopicSelector from '$lib/components/TopicSelector.svelte';
	import MathText from '$lib/components/MathText.svelte';
	import PdfQuestionView from '$lib/components/PdfQuestionView.svelte';
	import { formatScripts } from '$lib/formatText';
	import { celebrateFullMarks, celebrateCompletion } from '$lib/celebrations';
	import { shouldAnimate, DURATIONS } from '$lib/motion';

	type Correction = {
		subtopic_id: string;
		strand: string;
		topic: string;
		subtopic: string;
		spec_sub_section: string;
		description: string;
	};

	let session: any = $state(null);
	let loading = $state(true);
	let error = $state('');
	let ready = $state(false);

	let pendingMarks = new Map<number, number>();
	let saveTimeout: ReturnType<typeof setTimeout> | null = null;
	let saveStatus: 'idle' | 'saving' | 'saved' | 'error' = $state('idle');

	let currentMarks = $state(new Map<number, number>());
	let expandedDescs = $state(new Set<string>());

	// Track which questions have had full marks celebration
	let celebratedFullMarks = new Set<number>();
	let allMarkedCelebrated = false;

	// Corrections state: question_id -> array of corrections
	let correctionsMap = $state(new Map<number, Correction[]>());
	let dirtyCorrections = new Set<number>();
	let correctionSaveTimeout: ReturnType<typeof setTimeout> | null = null;

	// Spec sub section -> subtopic_id lookup (built from hierarchy)
	let specSubSectionToId = new Map<string, string>();

	let pendingQuestionEdits = new Map<number, { question_text?: string; marks_available?: number }>();
	let questionEditTimeout: ReturnType<typeof setTimeout> | null = null;

	// Per-question PDF view toggle: set of question_ids currently showing PDF
	let pdfViewQuestions = $state(new Set<number>());
	let downloadingPdf = $state(false);

	async function handleDownloadPdf() {
		if (!session) return;
		downloadingPdf = true;
		try {
			const blob = await downloadSessionPdf(session.session_id);
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = `${getTitle(session).replace(/[^a-zA-Z0-9 ]/g, '')}.pdf`;
			a.click();
			URL.revokeObjectURL(url);
		} catch (err) {
			console.error('Failed to download PDF:', err);
		} finally {
			downloadingPdf = false;
		}
	}

	function toggleQuestionView(questionId: number) {
		const next = new Set(pdfViewQuestions);
		if (next.has(questionId)) {
			next.delete(questionId);
		} else {
			next.add(questionId);
		}
		pdfViewQuestions = next;
	}

	function handleQuestionTextInput(questionId: number, value: string) {
		const existing = pendingQuestionEdits.get(questionId) ?? {};
		pendingQuestionEdits.set(questionId, { ...existing, question_text: value });
		saveStatus = 'saving';
		if (questionEditTimeout) clearTimeout(questionEditTimeout);
		questionEditTimeout = setTimeout(() => saveQuestionEdits(), 600);
	}

	function handleMarksAvailableInput(questionId: number, value: string, question: any) {
		if (value.trim() === '') return;
		const marks = parseInt(value, 10);
		if (Number.isNaN(marks) || marks < 0) return;

		question.marks_available = marks;
		const existing = pendingQuestionEdits.get(questionId) ?? {};
		pendingQuestionEdits.set(questionId, { ...existing, marks_available: marks });
		saveStatus = 'saving';
		if (questionEditTimeout) clearTimeout(questionEditTimeout);
		questionEditTimeout = setTimeout(() => saveQuestionEdits(), 600);
	}

	async function saveQuestionEdits() {
		if (pendingQuestionEdits.size === 0) {
			saveStatus = 'idle';
			return;
		}

		const edits = new Map(pendingQuestionEdits);
		pendingQuestionEdits.clear();

		try {
			for (const [questionId, data] of edits) {
				await updateQuestion(session.session_id, questionId, data);
			}
			saveStatus = 'saved';
		} catch (err) {
			console.error('Failed to save question edits:', err);
			saveStatus = 'error';
		}
	}

	onMount(async () => {
		const sessionId = $page.params.session_id;

		if (!sessionId) {
			error = 'No session ID provided';
			loading = false;
			return;
		}

		try {
			session = await getSession(sessionId);
			const initial = new Map<number, number>();
			const initialCorrections = new Map<number, Correction[]>();
			for (const q of session.questions) {
				if (q.marks_achieved != null) {
					initial.set(q.question_id, q.marks_achieved);
				}
				if (q.user_corrections && q.user_corrections.length > 0) {
					initialCorrections.set(q.question_id, [...q.user_corrections]);
				}
			}
			currentMarks = initial;
			correctionsMap = initialCorrections;

			// Pre-populate celebrated set for already full-marks questions
			for (const q of session.questions) {
				if (q.marks_achieved != null && q.marks_available != null && q.marks_achieved >= q.marks_available) {
					celebratedFullMarks.add(q.question_id);
				}
			}

			// Build spec_sub_section -> subtopic_id lookup from hierarchy
			try {
				const hierarchy = await getTopicHierarchy(session.spec_code);
				for (const strand of hierarchy.strands) {
					for (const topic of strand.topics) {
						for (const subtopic of topic.subtopics) {
							specSubSectionToId.set(subtopic.spec_sub_section, subtopic.subtopic_id);
						}
					}
				}
			} catch (e) {
				console.error('Failed to load hierarchy for subtopic ID lookup:', e);
			}
		} catch (err: any) {
			const msg = err.message || '';
			if (msg.includes('403')) {
				error = 'You are not authorized to view this session.';
			} else if (msg.includes('404')) {
				error = 'Session not found.';
			} else {
				error = `Failed to load session: ${msg}`;
			}
		} finally {
			loading = false;
			ready = true;
		}
	});

	function formatDate(dateStr: string): string {
		return new Date(dateStr).toLocaleDateString('en-GB', {
			day: 'numeric',
			month: 'long',
			year: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		});
	}

	function getTitle(s: any): string {
		const parts = [s.qualification, s.subject_name].filter(Boolean);
		return parts.length > 0 ? parts.join(' ') : s.subject;
	}

	function toggleDesc(descId: string) {
		const next = new Set(expandedDescs);
		if (next.has(descId)) {
			next.delete(descId);
		} else {
			next.add(descId);
		}
		expandedDescs = next;
	}

	function isMarksInvalid(questionId: number, marksAvailable: number | null): boolean {
		if (!currentMarks.has(questionId)) return false;
		const achieved = currentMarks.get(questionId)!;
		if (achieved < 0) return true;
		if (marksAvailable != null && achieved > marksAvailable) return true;
		return false;
	}

	function getMarksTier(questionId: number, marksAvailable: number | null): string {
		if (!currentMarks.has(questionId)) return '';
		if (isMarksInvalid(questionId, marksAvailable)) return 'marks-invalid';
		if (marksAvailable == null) return '';

		const achieved = currentMarks.get(questionId)!;
		if (achieved === 0) return 'marks-zero';

		const ratio = achieved / marksAvailable;
		if (ratio >= 1) return 'marks-full';
		if (ratio >= 0.75) return 'marks-high';
		return 'marks-mid';
	}

	function handleMarksInput(questionId: number, value: string, marksAvailable: number | null) {
		if (value.trim() === '') {
			pendingMarks.delete(questionId);
			const next = new Map(currentMarks);
			next.delete(questionId);
			currentMarks = next;
			return;
		}

		const marks = parseInt(value, 10);
		if (Number.isNaN(marks)) return;

		currentMarks = new Map(currentMarks).set(questionId, marks);

		if (marks < 0 || (marksAvailable != null && marks > marksAvailable)) {
			pendingMarks.delete(questionId);
			return;
		}

		pendingMarks.set(questionId, marks);
		saveStatus = 'saving';

		// Check for full marks celebration
		if (marksAvailable != null && marks >= marksAvailable && !celebratedFullMarks.has(questionId)) {
			celebratedFullMarks.add(questionId);
			celebrateFullMarks();
		}

		if (saveTimeout) clearTimeout(saveTimeout);
		saveTimeout = setTimeout(() => {
			saveChanges();
			checkAllMarked();
		}, 600);
	}

	function checkAllMarked() {
		if (!session || allMarkedCelebrated) return;
		const allMarked = session.questions.every((q: any) => currentMarks.has(q.question_id));
		if (allMarked) {
			allMarkedCelebrated = true;
			setTimeout(() => celebrateCompletion(), 300);
		}
	}

	function getCorrections(questionId: number): Correction[] {
		return correctionsMap.get(questionId) ?? [];
	}

	function isPredictionSelected(questionId: number, pred: any): boolean {
		const corrections = getCorrections(questionId);
		return corrections.some((c) => c.spec_sub_section === pred.spec_sub_section);
	}

	function togglePredictionAsCorrection(questionId: number, pred: any) {
		const corrections = getCorrections(questionId);
		const existing = corrections.find((c) => c.spec_sub_section === pred.spec_sub_section);

		if (existing) {
			const updated = corrections.filter((c) => c.spec_sub_section !== pred.spec_sub_section);
			correctionsMap = new Map(correctionsMap).set(questionId, updated);
		} else {
			const subtopicId = specSubSectionToId.get(pred.spec_sub_section) ?? '';
			const newCorrection: Correction = {
				subtopic_id: subtopicId,
				strand: pred.strand,
				topic: pred.topic,
				subtopic: pred.subtopic,
				spec_sub_section: pred.spec_sub_section,
				description: pred.description
			};
			correctionsMap = new Map(correctionsMap).set(questionId, [...corrections, newCorrection]);
		}

		scheduleCorrectionSave(questionId);
	}

	function handleCorrectionsChange(questionId: number, corrections: Correction[]) {
		correctionsMap = new Map(correctionsMap).set(questionId, corrections);
		scheduleCorrectionSave(questionId);
	}

	function scheduleCorrectionSave(questionId: number) {
		dirtyCorrections.add(questionId);
		saveStatus = 'saving';
		if (correctionSaveTimeout) clearTimeout(correctionSaveTimeout);
		correctionSaveTimeout = setTimeout(() => flushCorrections(), 600);
	}

	async function flushCorrections() {
		if (dirtyCorrections.size === 0) {
			saveStatus = 'idle';
			return;
		}

		const toSave = [...dirtyCorrections];
		dirtyCorrections.clear();

		const corrections = toSave.map((qId) => ({
			question_id: qId,
			subtopic_ids: (correctionsMap.get(qId) ?? []).map((c) => c.subtopic_id)
		}));

		try {
			await saveUserCorrections(session.session_id, corrections);
			saveStatus = 'saved';
		} catch (err) {
			console.error('Failed to save corrections:', err);
			saveStatus = 'error';
		}
	}

	async function saveChanges() {
		if (pendingMarks.size === 0) {
			saveStatus = 'idle';
			return;
		}

		const marksArray = Array.from(pendingMarks.entries()).map(([question_id, marks_achieved]) => ({
			question_id,
			marks_achieved
		}));

		pendingMarks.clear();

		try {
			await uploadAchievedMarks(session.session_id, marksArray);
			saveStatus = 'saved';
		} catch (err) {
			console.error('Failed to save marks:', err);
			saveStatus = 'error';
		}
	}

	function staggerDelay(i: number): number {
		return shouldAnimate() ? i * DURATIONS.stagger : 0;
	}
</script>

<svelte:head>
	<title>Session Details - Topic Tracker</title>
</svelte:head>

<main class="page-content">
	<a href="/history" class="btn-secondary back-link">Back to History</a>

	{#if loading}
		<div class="loading">
			<span class="loading-spinner"></span>
			Loading session...
		</div>
	{:else if error}
		<div class="error-state" in:fade={{ duration: 200 }}>
			<p>{error}</p>
			<p><a href="/history">Return to My Sessions</a></p>
		</div>
	{:else if session}
		{#if saveStatus !== 'idle'}
			<span class="save-indicator {saveStatus}" in:fly={{ x: 20, duration: 200 }}>
				{#if saveStatus === 'saving'}Saving...{/if}
				{#if saveStatus === 'saved'}Saved{/if}
				{#if saveStatus === 'error'}Save failed{/if}
			</span>
		{/if}

		<div class="session-header" in:fly={{ y: 15, duration: 300 }}>
			<h2>{getTitle(session)}</h2>
			<p class="session-meta">{session.exam_board} - {formatDate(session.created_at)}</p>
			{#if session.session_strands && session.session_strands.length > 0}
				<div class="session-strands">
					{#each session.session_strands as strand}
						<span class="strand-pill">{strand}</span>
					{/each}
				</div>
			{/if}
			{#if session.has_pdf}
				<button class="btn-download-pdf" onclick={handleDownloadPdf} disabled={downloadingPdf}>
					{downloadingPdf ? 'Downloading...' : 'Download the question paper PDF'}
				</button>
			{/if}
		</div>

		{#each session.questions as question, i}
			<div
				class="question-block"
				class:full-marks-glow={getMarksTier(question.question_id, question.marks_available) === 'marks-full'}
				in:fly={{ y: 20, duration: 300, delay: staggerDelay(i) }}
			>
				<div class="question-header">
					<h3>Question {question.question_number}:</h3>
					{#if question.pdf_location}
						<button
							class="toggle-btn {pdfViewQuestions.has(question.question_id) ? 'active' : ''}"
							tabindex="-1"
							onclick={() => toggleQuestionView(question.question_id)}
						>
							{pdfViewQuestions.has(question.question_id) ? 'View Text' : 'View PDF'}
						</button>
					{/if}
				</div>
				{#if pdfViewQuestions.has(question.question_id) && question.pdf_location}
					<PdfQuestionView
						sessionId={session.session_id}
						pdfLocation={question.pdf_location}
					/>
				{:else}
					<MathText
						text={question.question_text}
						onchange={(newText) => {
							question.question_text = newText;
							handleQuestionTextInput(question.question_id, newText);
						}}
					/>
				{/if}
				<div class="marks-available-row">
					<span class="marks-label">(</span>
					<input
						type="number"
						class="editable-marks-available"
						tabindex="-1"
						value={question.marks_available ?? ''}
						placeholder="Marks"
						min="0"
						oninput={(e) => handleMarksAvailableInput(question.question_id, e.currentTarget.value, question)}
					/>
					<span class="marks-label">)</span>
				</div>

				<input
					type="number"
					class="marks-achieved {getMarksTier(question.question_id, question.marks_available)}"
					placeholder="Marks achieved"
					value={question.marks_achieved ?? ''}
					oninput={(e) => handleMarksInput(question.question_id, e.currentTarget.value, question.marks_available)}
				/>
				{#if isMarksInvalid(question.question_id, question.marks_available)}
					<p class="marks-error" in:fade={{ duration: 150 }}>Please enter a value between 0 and {question.marks_available ?? '?'}</p>
				{/if}

				{#each question.predictions as pred}
					{@const selected = isPredictionSelected(question.question_id, pred)}
					<div class="prediction">
						<p>
							Rank {pred.rank}: {pred.strand} &rarr; {pred.topic} &rarr;
							<span
								class="subtopic clickable"
								role="button"
								tabindex="-1"
								onclick={() => toggleDesc(`desc-${question.question_id}-${pred.rank}`)}
								onkeydown={(e) => {
									if (e.key === 'Enter' || e.key === ' ') {
										e.preventDefault();
										toggleDesc(`desc-${question.question_id}-${pred.rank}`);
									}
								}}
							>
								{@html formatScripts(pred.subtopic)}
							</span>
							(Similarity score {pred.similarity_score.toFixed(3)})
							<button
								class="btn-select-pred {selected ? 'selected' : ''}"
								tabindex="-1"
								onclick={() => togglePredictionAsCorrection(question.question_id, pred)}
							>
								{selected ? 'Selected' : 'Select'}
							</button>
						</p>
						{#if expandedDescs.has(`desc-${question.question_id}-${pred.rank}`)}
							<div class="description" transition:slide={{ duration: 200 }}>
								{@html formatScripts(pred.description)}
							</div>
						{/if}
					</div>
				{/each}

				<TopicSelector
					specCode={session.spec_code}
					corrections={getCorrections(question.question_id)}
					onchange={(c) => handleCorrectionsChange(question.question_id, c)}
				/>
			</div>
		{/each}
	{/if}
</main>

<style>
	.loading-spinner {
		display: inline-block;
		width: 18px;
		height: 18px;
		border: 2.5px solid var(--color-border);
		border-top-color: var(--color-primary);
		border-radius: 50%;
		animation: spin 0.7s linear infinite;
		vertical-align: middle;
		margin-right: 8px;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	.session-strands {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		margin-top: 8px;
	}

	.strand-pill {
		display: inline-block;
		padding: 4px 14px;
		border-radius: var(--radius-full);
		background: var(--color-primary-light);
		color: #0F766E;
		font-size: 0.85rem;
		font-weight: 600;
	}

	.question-header {
		display: flex;
		align-items: center;
	}

	.question-header h3 {
		margin: 0;
	}

	.toggle-btn {
		width: auto;
		margin-left: auto;
		padding: 6px 10px;
		border: 1.5px solid var(--color-border);
		border-radius: var(--radius-sm);
		background: var(--color-surface);
		color: var(--color-text-secondary);
		font-size: 0.75rem;
		font-weight: 600;
		cursor: pointer;
		transition: all var(--transition-fast);
		line-height: 1;
		margin-bottom: 4px;
	}

	.toggle-btn:hover {
		border-color: var(--color-primary);
		color: var(--color-primary);
	}

	.toggle-btn.active {
		background: var(--color-primary);
		color: #fff;
		border-color: var(--color-primary);
	}

	.btn-download-pdf {
		margin-top: 10px;
		padding: 8px 16px;
		border: 1.5px solid var(--color-border);
		border-radius: var(--radius-sm);
		background: var(--color-surface);
		color: var(--color-text);
		font-size: 0.9rem;
		font-weight: 600;
		font-family: var(--font-body);
		cursor: pointer;
		transition: all var(--transition-fast);
	}

	.btn-download-pdf:hover:not(:disabled) {
		border-color: var(--color-primary);
		color: var(--color-primary);
	}

	.btn-download-pdf:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.full-marks-glow {
		border-color: var(--color-success) !important;
		box-shadow: 0 0 0 2px var(--color-success-bg), var(--shadow-md) !important;
	}
</style>
