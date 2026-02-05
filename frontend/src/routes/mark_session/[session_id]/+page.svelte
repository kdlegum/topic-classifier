<script lang="ts">
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import { getSession, uploadAchievedMarks, updateQuestion, getTopicHierarchy, saveUserCorrections } from '$lib/api';
	import TopicSelector from '$lib/components/TopicSelector.svelte';

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

	let pendingMarks = new Map<number, number>();
	let saveTimeout: ReturnType<typeof setTimeout> | null = null;
	let saveStatus: 'idle' | 'saving' | 'saved' | 'error' = $state('idle');

	let currentMarks = $state(new Map<number, number>());
	let expandedDescs = $state(new Set<string>());

	// Corrections state: question_id -> array of corrections
	let correctionsMap = $state(new Map<number, Correction[]>());
	let dirtyCorrections = new Set<number>();
	let correctionSaveTimeout: ReturnType<typeof setTimeout> | null = null;

	// Spec sub section -> subtopic_id lookup (built from hierarchy)
	let specSubSectionToId = new Map<string, string>();

	let pendingQuestionEdits = new Map<number, { question_text?: string; marks_available?: number }>();
	let questionEditTimeout: ReturnType<typeof setTimeout> | null = null;

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

	function autoResize(textarea: HTMLTextAreaElement) {
		textarea.style.height = 'auto';
		textarea.style.height = textarea.scrollHeight + 'px';
		return {};
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

		if (saveTimeout) clearTimeout(saveTimeout);
		saveTimeout = setTimeout(() => saveChanges(), 600);
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
</script>

<svelte:head>
	<title>Session Details - Topic Tracker</title>
</svelte:head>

<main class="page-content">
	<a href="/history" class="btn-secondary back-link">Back to History</a>

	{#if loading}
		<div class="loading">Loading session...</div>
	{:else if error}
		<div class="error-state">
			<p>{error}</p>
			<p><a href="/history">Return to My Sessions</a></p>
		</div>
	{:else if session}
		{#if saveStatus !== 'idle'}
			<span class="save-indicator {saveStatus}">
				{#if saveStatus === 'saving'}Saving...{/if}
				{#if saveStatus === 'saved'}Saved{/if}
				{#if saveStatus === 'error'}Save failed{/if}
			</span>
		{/if}

		<div class="session-header">
			<h2>{getTitle(session)}</h2>
			<p class="session-meta">{session.exam_board} - {formatDate(session.created_at)}</p>
		</div>

		{#each session.questions as question}
			<div class="question-block">
				<h3>Question {question.question_number}:</h3>
				<textarea
					class="editable-question-text"
					value={question.question_text}
					oninput={(e) => {
						const ta = e.currentTarget;
						autoResize(ta);
						handleQuestionTextInput(question.question_id, ta.value);
					}}
					use:autoResize
				></textarea>
				<div class="marks-available-row">
					<span class="marks-label">(</span>
					<input
						type="number"
						class="editable-marks-available"
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
					<p class="marks-error">Please enter a value between 0 and {question.marks_available ?? '?'}</p>
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
								{pred.subtopic}
							</span>
							(Similarity score {pred.similarity_score})
							<button
								class="btn-select-pred {selected ? 'selected' : ''}"
								onclick={() => togglePredictionAsCorrection(question.question_id, pred)}
							>
								{selected ? 'Selected' : 'Select'}
							</button>
						</p>
						{#if expandedDescs.has(`desc-${question.question_id}-${pred.rank}`)}
							<div class="description">
								{pred.description}
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
