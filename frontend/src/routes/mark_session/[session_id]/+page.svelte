<script lang="ts">
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import { getSession, uploadAchievedMarks } from '$lib/api';

	let session: any = $state(null);
	let loading = $state(true);
	let error = $state('');

	let pendingMarks = new Map<number, number>();
	let saveTimeout: ReturnType<typeof setTimeout> | null = null;
	let saveStatus: 'idle' | 'saving' | 'saved' | 'error' = $state('idle');

	let currentMarks = $state(new Map<number, number>());
	let expandedDescs = $state(new Set<string>());

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
			for (const q of session.questions) {
				if (q.marks_achieved != null) {
					initial.set(q.question_id, q.marks_achieved);
				}
			}
			currentMarks = initial;
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
				<p>{question.question_text}</p>
				<p class="total_marks">
					{question.marks_available === null
						? 'Marks Not found'
						: `(${question.marks_available})`}
				</p>

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
						</p>
						{#if expandedDescs.has(`desc-${question.question_id}-${pred.rank}`)}
							<div class="description">
								{pred.description}
							</div>
						{/if}
					</div>
				{/each}
			</div>
		{/each}
	{/if}
</main>
