<script lang="ts">
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import { fly, fade, slide } from 'svelte/transition';
	import { getSession, uploadAchievedMarks, updateQuestion, getTopicHierarchy, saveUserCorrections, downloadSessionPdf, uploadMarkScheme, downloadMarkSchemePdf, renameSession } from '$lib/api';
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
	let nameSaveTimeout: ReturnType<typeof setTimeout> | null = null;

	// Per-question PDF view toggle: set of question_ids currently showing PDF
	let pdfViewQuestions = $state(new Set<number>());
	let downloadingPdf = $state(false);
	let markSchemeInput: HTMLInputElement;
	let markSchemeUploading = $state(false);
	let markSchemeStatus = $state('');


	// Keyboard shortcut state
	let currentQuestionId = $state<number | null>(null);
	let showShortcuts = $state(false);

	// ── Results panel ────────────────────────────────────────────────────────
	type TopicStat = { strand: string; topic: string; achieved: number; available: number; pct: number };

	let displayedScore = $state(0);
	let displayedPct = $state(0);
	let resultsAnimFrame: number | null = null;
	let resultsPanelEl: HTMLElement | null = $state(null);

	// Scroll to results panel when it appears
	$effect(() => {
		if (!resultsPanelEl) return;
		const el = resultsPanelEl;
		const timeout = setTimeout(() => {
			const scrollContainer = document.querySelector('.app-content') as HTMLElement | null;
			if (scrollContainer) {
				const containerRect = scrollContainer.getBoundingClientRect();
				const targetRect = el.getBoundingClientRect();
				const newScrollTop = scrollContainer.scrollTop + targetRect.top - containerRect.top - 24;
				scrollContainer.scrollTo({ top: newScrollTop, behavior: 'smooth' });
			}
		}, 100);
		return () => clearTimeout(timeout);
	});

	let allMarked = $derived(
		!!session &&
		session.questions.length > 0 &&
		session.questions.every((q: any) => currentMarks.has(q.question_id))
	);

	let totalAchieved = $derived(
		allMarked ? [...currentMarks.values()].reduce((a, b) => a + b, 0) : 0
	);
	let totalAvailable = $derived(
		allMarked ? session!.questions.reduce((sum: number, q: any) => sum + (q.marks_available ?? 0), 0) : 0
	);
	let percentage = $derived(totalAvailable > 0 ? Math.round((totalAchieved / totalAvailable) * 100) : null);

	let topicStats = $derived.by<TopicStat[]>(() => {
		if (!session || !allMarked) return [];
		const map = new Map<string, Omit<TopicStat, 'pct'>>();
		for (const q of session.questions) {
			const achieved = currentMarks.get(q.question_id);
			if (achieved == null || !q.marks_available) continue;
			const corrections = correctionsMap.get(q.question_id) ?? [];
			let strand = '', topic = '';
			if (corrections.length > 0) {
				strand = corrections[0].strand;
				topic = corrections[0].topic;
			} else {
				const rank1 = q.predictions?.find((p: any) => p.rank === 1);
				if (!rank1) continue;
				strand = rank1.strand;
				topic = rank1.topic;
			}
			const key = `${strand}||${topic}`;
			const existing = map.get(key) ?? { strand, topic, achieved: 0, available: 0 };
			map.set(key, { ...existing, achieved: existing.achieved + achieved, available: existing.available + q.marks_available });
		}
		return [...map.values()]
			.map(s => ({ ...s, pct: Math.round((s.achieved / s.available) * 100) }))
			.sort((a, b) => b.pct - a.pct);
	});

	let showN = $derived(Math.min(3, Math.floor(topicStats.length / 2)));
	let strongTopics = $derived(topicStats.slice(0, showN));
	let weakTopics = $derived([...topicStats].reverse().slice(0, showN));

	// Count-up animation for results panel
	$effect(() => {
		if (!allMarked) {
			displayedScore = 0;
			displayedPct = 0;
			if (resultsAnimFrame != null) { cancelAnimationFrame(resultsAnimFrame); resultsAnimFrame = null; }
			return;
		}
		const targetScore = totalAchieved;
		const targetPct = percentage ?? 0;
		const duration = 1400;
		const startTime = performance.now();
		if (resultsAnimFrame != null) cancelAnimationFrame(resultsAnimFrame);

		function easeOut(t: number) { return 1 - Math.pow(1 - t, 3); }
		function tick(now: number) {
			const elapsed = Math.min(now - startTime, duration);
			const t = easeOut(elapsed / duration);
			displayedScore = Math.round(t * targetScore);
			displayedPct = Math.round(t * targetPct);
			if (elapsed < duration) {
				resultsAnimFrame = requestAnimationFrame(tick);
			} else {
				displayedScore = targetScore;
				displayedPct = targetPct;
				resultsAnimFrame = null;
			}
		}
		resultsAnimFrame = requestAnimationFrame(tick);
		return () => { if (resultsAnimFrame != null) { cancelAnimationFrame(resultsAnimFrame); resultsAnimFrame = null; } };
	});

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

	async function handleDownloadMarkScheme() {
		if (!session) return;
		try {
			const blob = await downloadMarkSchemePdf(session.session_id);
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = `${getTitle(session).replace(/[^a-zA-Z0-9 ]/g, '')}_mark_scheme.pdf`;
			a.click();
			URL.revokeObjectURL(url);
		} catch (err) {
			console.error('Failed to download mark scheme:', err);
		}
	}

	async function handleMarkSchemeUpload(e: Event) {
		const input = e.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file || !session) return;
		markSchemeUploading = true;
		markSchemeStatus = 'Uploading...';
		try {
			await uploadMarkScheme(session.session_id, file);
			session.has_mark_scheme = true;
			markSchemeStatus = 'Done';
		} catch (err) {
			console.error('Failed to upload mark scheme:', err);
			markSchemeStatus = 'Upload failed';
		} finally {
			markSchemeUploading = false;
			input.value = '';
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

	function handleNameInput(e: Event) {
		const value = (e.target as HTMLElement).innerText.trim() || null;
		// Don't update session.name here — it causes Svelte to re-render the
		// contenteditable and reset the cursor to the start while typing.
		saveStatus = 'saving';
		if (nameSaveTimeout) clearTimeout(nameSaveTimeout);
		nameSaveTimeout = setTimeout(async () => {
			try {
				await renameSession(session.session_id, value);
				saveStatus = 'saved';
			} catch (err) {
				console.error('Failed to rename session:', err);
				saveStatus = 'error';
			}
		}, 600);
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

			// Build spec_sub_section -> subtopic_id lookup from hierarchy (skip for no-spec sessions)
			if (!session.no_spec) {
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
		if (s.no_spec) return 'Unclassified Session';
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

	function handleMarksKeydown(e: KeyboardEvent) {
		if (e.key !== 'Tab') return;
		const all = Array.from(document.querySelectorAll<HTMLInputElement>('.marks-achieved'));
		const idx = all.indexOf(e.currentTarget as HTMLInputElement);
		const next = all[idx + (e.shiftKey ? -1 : 1)];
		if (!next) return;
		e.preventDefault();
		next.focus({ preventScroll: true });
		const block = next.closest('.question-block') as HTMLElement | null;
		const target = block ?? next;
		const scrollContainer = document.querySelector('.app-content') as HTMLElement | null;
		if (scrollContainer) {
			const TOP_MARGIN = 24;
			const containerRect = scrollContainer.getBoundingClientRect();
			const targetRect = target.getBoundingClientRect();
			const newScrollTop = scrollContainer.scrollTop + targetRect.top - containerRect.top - TOP_MARGIN;
			scrollContainer.scrollTo({ top: newScrollTop, behavior: 'smooth' });
		}
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

	// ── Keyboard shortcut handlers ──────────────────────────────────────────

	function isTypingContext(e: KeyboardEvent): boolean {
		const target = e.target as HTMLElement;
		const tag = target.tagName.toLowerCase();
		if (tag === 'textarea') return true;
		if (target.contentEditable === 'true') return true;
		if (tag === 'input') {
			// Allow shortcuts from the marks-achieved input
			return !target.classList.contains('marks-achieved');
		}
		return false;
	}

	function handlePageFocusin(e: FocusEvent) {
		const target = e.target as HTMLElement;
		const block = target.closest('[data-question-id]') as HTMLElement | null;
		if (block) {
			const qId = parseInt(block.dataset.questionId ?? '');
			if (!isNaN(qId)) currentQuestionId = qId;
		}
	}

	function adjustMarksAvailable(questionId: number, delta: number) {
		const q = session?.questions.find((q: any) => q.question_id === questionId);
		if (!q) return;
		const current = q.marks_available ?? 0;
		const next = Math.max(0, current + delta);
		q.marks_available = next;
		const existing = pendingQuestionEdits.get(questionId) ?? {};
		pendingQuestionEdits.set(questionId, { ...existing, marks_available: next });
		saveStatus = 'saving';
		if (questionEditTimeout) clearTimeout(questionEditTimeout);
		questionEditTimeout = setTimeout(() => saveQuestionEdits(), 600);
	}

	function adjustMarks(questionId: number, delta: number) {
		const q = session?.questions.find((q: any) => q.question_id === questionId);
		if (!q) return;
		const current = currentMarks.get(questionId) ?? q.marks_achieved ?? 0;
		let next = current + delta;
		next = Math.max(0, next);
		if (q.marks_available != null) next = Math.min(next, q.marks_available);
		q.marks_achieved = next;
		handleMarksInput(questionId, String(next), q.marks_available);
	}

	function navigateQuestion(delta: number) {
		if (!session) return;
		const questions = session.questions;
		const currentIdx = currentQuestionId != null
			? questions.findIndex((q: any) => q.question_id === currentQuestionId)
			: -1;
		const nextIdx = Math.max(0, Math.min(questions.length - 1, currentIdx + delta));
		const nextQ = questions[nextIdx];
		if (!nextQ) return;
		currentQuestionId = nextQ.question_id;

		const block = document.querySelector(`[data-question-id="${nextQ.question_id}"]`) as HTMLElement | null;
		if (block) {
			const scrollContainer = document.querySelector('.app-content') as HTMLElement | null;
			if (scrollContainer) {
				const TOP_MARGIN = 24;
				const containerRect = scrollContainer.getBoundingClientRect();
				const targetRect = block.getBoundingClientRect();
				const newScrollTop = scrollContainer.scrollTop + targetRect.top - containerRect.top - TOP_MARGIN;
				scrollContainer.scrollTo({ top: newScrollTop, behavior: 'smooth' });
			}
		}
	}

	function handleGlobalKeydown(e: KeyboardEvent) {
		// Alt+= / Alt+- adjust total marks available
		if (e.altKey && !e.ctrlKey && !e.metaKey) {
			if ((e.key === '=' || e.key === '+') && currentQuestionId != null && !isTypingContext(e)) {
				e.preventDefault();
				adjustMarksAvailable(currentQuestionId, 1);
			} else if (e.key === '-' && currentQuestionId != null && !isTypingContext(e)) {
				e.preventDefault();
				adjustMarksAvailable(currentQuestionId, -1);
			}
			return;
		}

		if (e.ctrlKey || e.metaKey) return;

		if (e.key === '?' && !isTypingContext(e)) {
			e.preventDefault();
			showShortcuts = !showShortcuts;
			return;
		}

		if (e.key === 'Escape' && showShortcuts) {
			showShortcuts = false;
			return;
		}

		if (isTypingContext(e)) return;
		if (!session) return;

		switch (e.key) {
			case 'p': {
				if (currentQuestionId == null) break;
				const q = session.questions.find((q: any) => q.question_id === currentQuestionId);
				if (q?.pdf_location) {
					e.preventDefault();
					toggleQuestionView(currentQuestionId);
				}
				break;
			}
			// Shift+1/2/3 — works on both UK (!, ", £) and US (!, @, #) layouts
			case '!':
			case '"':
			case '@':
			case '£':
			case '#': {
				if (currentQuestionId == null) break;
				const rank = e.key === '!' ? 1 : (e.key === '"' || e.key === '@') ? 2 : 3;
				const q = session.questions.find((q: any) => q.question_id === currentQuestionId);
				const pred = q?.predictions.find((p: any) => p.rank === rank);
				if (pred) {
					e.preventDefault();
					togglePredictionAsCorrection(currentQuestionId, pred);
				}
				break;
			}
			case '+':
			case '=':
				if (currentQuestionId != null) {
					e.preventDefault();
					adjustMarks(currentQuestionId, 1);
				}
				break;
			case '-':
			case '_':
				if (currentQuestionId != null) {
					e.preventDefault();
					adjustMarks(currentQuestionId, -1);
				}
				break;
			case 'j':
				e.preventDefault();
				navigateQuestion(-1);
				break;
			case 'k':
				e.preventDefault();
				navigateQuestion(1);
				break;
		}
	}
</script>

<svelte:window onkeydown={handleGlobalKeydown} />

<svelte:head>
	<title>Session Details - Topic Tracker</title>
</svelte:head>

<main class="page-content" onfocusin={handlePageFocusin}>
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
			<!-- svelte-ignore a11y-interactive-supports-focus -->
			<h2
				class="session-name-edit"
				contenteditable="true"
				role="textbox"
				aria-label="Session name"
				spellcheck="false"
				oninput={handleNameInput}
				onkeydown={(e) => { if (e.key === 'Enter') { e.preventDefault(); (e.target as HTMLElement).blur(); } }}
			>{session.name ?? getTitle(session)}</h2>
			<p class="session-meta">
				{session.no_spec ? 'No specification' : session.exam_board}{#if session.paper_number || session.paper_name} &middot; {session.paper_name ?? `Paper ${session.paper_number}`}{#if session.paper_year} &middot; {session.paper_series ? session.paper_series.charAt(0).toUpperCase() + session.paper_series.slice(1) : ''} {session.paper_year}{/if}{/if} - {formatDate(session.created_at)}
			</p>
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
			{#if session.has_mark_scheme}
				<div class="btn-row">
					<button class="btn-download-pdf" onclick={handleDownloadMarkScheme}>
						Download Mark Scheme
					</button>
					<label class="btn-replace-ms">
						Replace
						<input type="file" accept="application/pdf" class="file-input-hidden" onchange={handleMarkSchemeUpload} />
					</label>
				</div>
			{:else}
				<label class="btn-upload-ms" class:uploading={markSchemeUploading}>
					{markSchemeUploading ? markSchemeStatus : markSchemeStatus === 'Done' ? 'Done' : 'Upload Mark Scheme'}
					<input type="file" accept="application/pdf" class="file-input-hidden" onchange={handleMarkSchemeUpload} disabled={markSchemeUploading} />
				</label>
			{/if}
		</div>

		{#if session.no_spec}
			<div class="no-spec-banner" in:fly={{ y: 10, duration: 250 }}>
				No specification selected — topic predictions are not available for this session.
			</div>
		{/if}

		{#each session.questions as question, i}
			<div
				class="question-block"
				class:full-marks-glow={getMarksTier(question.question_id, question.marks_available) === 'marks-full'}
				class:current-question={currentQuestionId === question.question_id}
				data-question-id={question.question_id}
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
					onkeydown={handleMarksKeydown}
				/>
				{#if isMarksInvalid(question.question_id, question.marks_available)}
					<p class="marks-error" in:fade={{ duration: 150 }}>Please enter a value between 0 and {question.marks_available ?? '?'}</p>
				{/if}

			{#if !session.no_spec}
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
				{/if}

				{#if !session.no_spec}
				<TopicSelector
					specCode={session.spec_code}
					corrections={getCorrections(question.question_id)}
					onchange={(c) => handleCorrectionsChange(question.question_id, c)}
				/>
			{/if}
			</div>
		{/each}

	{#if allMarked}
		{@const pctClass = (percentage ?? 0) >= 75 ? 'pct-high' : (percentage ?? 0) >= 50 ? 'pct-mid' : 'pct-low'}
		<div class="results-panel" bind:this={resultsPanelEl} in:fly={{ y: 30, duration: 500 }}>
			<div class="results-score-row">
				<div class="results-score">
					<span class="score-num">{displayedScore}</span>
					<span class="score-sep">/</span>
					<span class="score-total">{totalAvailable}</span>
				</div>
				{#if percentage != null}
					<div class="score-pct-badge {pctClass}">{displayedPct}%</div>
				{/if}
			</div>
			{#if !session.no_spec && showN >= 1}
				<hr class="results-divider" />
				<div class="topic-breakdown">
					{#if strongTopics.length > 0}
						<div class="topic-col">
							<p class="topic-col-label strongest-label">Strongest</p>
							{#each strongTopics as stat}
								<div class="topic-stat-row">
									<span class="topic-stat-name">{stat.topic}</span>
									<div class="topic-bar-wrap">
										<div class="topic-bar topic-bar-strong" style="--w: {stat.pct}%"></div>
									</div>
									<span class="topic-stat-pct">{stat.pct}%</span>
								</div>
							{/each}
						</div>
					{/if}
					{#if weakTopics.length > 0}
						<div class="topic-col">
							<p class="topic-col-label weakest-label">Needs work</p>
							{#each weakTopics as stat}
								<div class="topic-stat-row">
									<span class="topic-stat-name">{stat.topic}</span>
									<div class="topic-bar-wrap">
										<div class="topic-bar topic-bar-weak" style="--w: {stat.pct}%"></div>
									</div>
									<span class="topic-stat-pct">{stat.pct}%</span>
								</div>
							{/each}
						</div>
					{/if}
				</div>
			{/if}
		</div>
	{/if}
	{/if}
</main>

<!-- Floating shortcuts help button -->
<button class="shortcuts-fab" onclick={() => showShortcuts = !showShortcuts} title="Keyboard shortcuts (?)">
	?
</button>

<!-- Shortcuts modal -->
{#if showShortcuts}
	<div
		class="shortcuts-backdrop"
		onclick={() => showShortcuts = false}
		in:fade={{ duration: 150 }}
		out:fade={{ duration: 150 }}
	>
		<div
			class="shortcuts-modal"
			onclick={(e) => e.stopPropagation()}
			in:fly={{ y: -8, duration: 200 }}
			out:fly={{ y: -8, duration: 150 }}
		>
			<div class="shortcuts-header">
				<h3>Keyboard Shortcuts</h3>
				<button class="shortcuts-close" onclick={() => showShortcuts = false}>✕</button>
			</div>
			<table class="shortcuts-table">
				<tbody>
					<tr>
						<td><kbd>k</kbd> <kbd>j</kbd></td>
						<td>Next / previous question</td>
					</tr>
					<tr>
						<td><kbd>!</kbd> <kbd>"</kbd> <kbd>£</kbd></td>
						<td>Select rank 1 / 2 / 3 prediction</td>
					</tr>
					<tr>
						<td><kbd>p</kbd></td>
						<td>Toggle PDF view</td>
					</tr>
					<tr>
						<td><kbd>+</kbd> <kbd>-</kbd></td>
						<td>Increase / decrease achieved marks</td>
					</tr>
					<tr>
						<td><kbd>Alt</kbd>+<kbd>=</kbd> / <kbd>Alt</kbd>+<kbd>-</kbd></td>
						<td>Increase / decrease total marks</td>
					</tr>
					<tr>
						<td><kbd>Tab</kbd></td>
						<td>Move between mark inputs</td>
					</tr>
					<tr>
						<td><kbd>?</kbd></td>
						<td>Show / hide this panel</td>
					</tr>
				</tbody>
			</table>
			<p class="shortcuts-note">Active from the marks input. Inactive in all other text fields.</p>
		</div>
	</div>
{/if}

<style>
	.session-name-edit {
		outline: none;
		border-bottom: 2px solid transparent;
		border-radius: 2px;
		padding-bottom: 2px;
		cursor: text;
		transition: border-color 0.15s;
	}

	.session-name-edit:hover {
		border-bottom-color: var(--color-border);
	}

	.session-name-edit:focus {
		border-bottom-color: var(--color-primary);
	}
	.no-spec-banner {
		margin-bottom: 16px;
		padding: 12px 16px;
		border-radius: var(--radius-sm);
		background: var(--color-surface-alt);
		border: 1.5px solid var(--color-border);
		color: var(--color-text-secondary);
		font-size: 0.9rem;
	}

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

	.btn-row {
		display: flex;
		align-items: stretch;
		gap: 8px;
		margin-top: 10px;
	}

	.btn-row .btn-download-pdf {
		flex: 1;
		margin-top: 0;
	}

	.btn-upload-ms {
		display: block;
		width: 100%;
		box-sizing: border-box;
		text-align: center;
		margin-top: 10px;
		padding: 8px 16px;
		border: 1.5px dashed var(--color-border);
		border-radius: var(--radius-sm);
		background: var(--color-surface);
		color: var(--color-text-secondary);
		font-size: 0.9rem;
		font-weight: 600;
		font-family: var(--font-body);
		cursor: pointer;
		transition: all var(--transition-fast);
	}

	.btn-upload-ms:hover {
		border-color: var(--color-primary);
		color: var(--color-primary);
	}

	.btn-replace-ms {
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 0 16px;
		border: 1.5px solid var(--color-border);
		border-radius: var(--radius-sm);
		background: var(--color-surface);
		color: var(--color-text-secondary);
		font-size: 0.9rem;
		font-weight: 600;
		font-family: var(--font-body);
		cursor: pointer;
		transition: all var(--transition-fast);
		white-space: nowrap;
	}

	.btn-replace-ms:hover {
		border-color: var(--color-primary);
		color: var(--color-primary);
	}

	.file-input-hidden {
		position: absolute;
		width: 1px;
		height: 1px;
		opacity: 0;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
		margin: 0;
	}

	.full-marks-glow {
		border-color: var(--color-success) !important;
		box-shadow: 0 0 0 2px var(--color-success-bg), var(--shadow-md) !important;
	}

	.current-question {
		border-color: var(--color-primary) !important;
		box-shadow: 0 0 0 2px var(--color-primary-light), var(--shadow-md) !important;
	}

	/* ── Shortcuts FAB ── */
	.shortcuts-fab {
		position: fixed;
		bottom: 24px;
		right: 24px;
		width: 36px;
		height: 36px;
		border-radius: 50%;
		border: 1.5px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text-secondary);
		font-size: 1rem;
		font-weight: 700;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		box-shadow: var(--shadow-md);
		transition: all var(--transition-fast);
		z-index: 100;
	}

	.shortcuts-fab:hover {
		border-color: var(--color-primary);
		color: var(--color-primary);
	}

	/* ── Shortcuts modal ── */
	.shortcuts-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.4);
		z-index: 200;
		display: flex;
		align-items: center;
		justify-content: center;
		backdrop-filter: blur(2px);
	}

	.shortcuts-modal {
		position: relative;
		background: #ffffff;
		border-radius: 16px;
		padding: 32px;
		width: 100%;
		max-width: 440px;
		box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
		color: #1a1a1a;
	}

	.shortcuts-header {
		margin-bottom: 24px;
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.shortcuts-header h3 {
		margin: 0;
		font-family: "Source Serif Pro", serif; /* Or your preferred serif display font */
		font-size: 1.5rem;
		font-weight: 600;
		color: #111827;
	}

	.shortcuts-close {
		background: #f3f4f6;
		border: none;
		cursor: pointer;
		color: #6b7280;
		width: 32px;
		height: 32px;
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.2s;
	}

	.shortcuts-close:hover {
		background: #e5e7eb;
		color: #111827;
	}

	.shortcuts-table {
		width: 100%;
		border-collapse: collapse;
	}

	.shortcuts-table td {
		padding: 10px 0;
		vertical-align: middle;
		border-bottom: 1px solid #f3f4f6;
	}

	.shortcuts-table tr:last-child td {
		border-bottom: none;
	}

	.shortcuts-table td:first-child {
		padding-right: 20px;
		white-space: nowrap;
		min-width: 110px;
	}

	.shortcuts-table td:last-child {
		color: #4b5563;
		font-size: 0.95rem;
		font-weight: 400;
	}

	/* Tactile Keyboard Styling */
	kbd {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-width: 24px;
		padding: 4px 8px;
		font-family: system-ui, -apple-system, sans-serif;
		font-size: 0.85rem;
		font-weight: 700;
		line-height: 1;
		color: #374151;
		background: #fafafa;
		border: 1px solid #d1d5db;
		border-radius: 6px;
		box-shadow: 0 2px 0 #d1d5db;
		margin-right: 4px;
	}

	.shortcuts-note {
		margin: 20px 0 0;
		font-size: 0.85rem;
		color: #6b7280;
		background: #f9fafb;
		padding: 12px 16px;
		border-radius: 8px;
		text-align: center;
	}

	/* ── Results Panel ── */
	.results-panel {
		margin-top: 24px;
		padding: 28px 28px 24px;
		background: var(--color-surface);
		border: 1.5px solid var(--color-primary);
		border-radius: var(--radius-lg);
		box-shadow: 0 0 0 4px var(--color-primary-glow), var(--shadow-lg);
	}

	.results-score-row {
		display: flex;
		align-items: center;
		gap: 18px;
		flex-wrap: wrap;
	}

	.results-score {
		display: flex;
		align-items: baseline;
		gap: 6px;
	}

	.score-num {
		font-family: var(--font-heading);
		font-size: 3.2rem;
		font-weight: 700;
		color: var(--color-text);
		line-height: 1;
		letter-spacing: -0.02em;
	}

	.score-sep {
		font-family: var(--font-heading);
		font-size: 2rem;
		color: var(--color-text-muted);
		font-weight: 300;
		line-height: 1;
	}

	.score-total {
		font-family: var(--font-heading);
		font-size: 1.6rem;
		color: var(--color-text-secondary);
		font-weight: 400;
		line-height: 1;
	}

	.score-pct-badge {
		margin-left: 4px;
		padding: 6px 18px;
		border-radius: var(--radius-full);
		font-family: var(--font-heading);
		font-size: 1.25rem;
		font-weight: 700;
	}

	.score-pct-badge.pct-high {
		background: var(--color-success-bg);
		color: #15803d;
	}

	.score-pct-badge.pct-mid {
		background: var(--color-warning-bg);
		color: #b45309;
	}

	.score-pct-badge.pct-low {
		background: var(--color-error-bg);
		color: #b91c1c;
	}

	.results-divider {
		border: none;
		border-top: 1px solid var(--color-border);
		margin: 20px 0;
	}

	.topic-breakdown {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 24px;
	}

	.topic-col {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}

	.topic-col-label {
		margin: 0 0 2px;
		font-size: 0.72rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}

	.strongest-label {
		color: #15803d;
	}

	.weakest-label {
		color: #b91c1c;
	}

	.topic-stat-row {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.topic-stat-name {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: 0.88rem;
		color: var(--color-text);
	}

	.topic-bar-wrap {
		width: 80px;
		flex-shrink: 0;
		height: 6px;
		background: var(--color-border);
		border-radius: 3px;
		overflow: hidden;
	}

	.topic-bar {
		height: 100%;
		border-radius: 3px;
		width: var(--w);
		animation: barGrow 0.9s cubic-bezier(0.16, 1, 0.3, 1) both;
		animation-delay: 0.6s;
	}

	.topic-bar-strong {
		background: var(--color-success);
	}

	.topic-bar-weak {
		background: var(--color-error);
	}

	@keyframes barGrow {
		from { width: 0; }
		to { width: var(--w); }
	}

	.topic-stat-pct {
		font-size: 0.82rem;
		font-weight: 700;
		color: var(--color-text-secondary);
		min-width: 36px;
		text-align: right;
	}

	@media (max-width: 480px) {
		.topic-breakdown {
			grid-template-columns: 1fr;
		}
	}
</style>
