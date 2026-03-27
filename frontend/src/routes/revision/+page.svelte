<script lang="ts">
	import { onMount } from 'svelte';
	import { fly, fade, slide } from 'svelte/transition';
	import { cubicIn, cubicOut } from 'svelte/easing';
	import { getRevisionPool, recordRevisionAttempt, downloadSessionPdf, downloadSessionMarkScheme, getSpecs, getQuickPractice, downloadQuickPracticeMarkScheme, downloadQuickPracticePdf } from '$lib/api';
	import type { RevisionQuestion, QuickPracticeQuestion, SpecInfo } from '$lib/api';
	import MathText from '$lib/components/MathText.svelte';
	import PdfQuestionView from '$lib/components/PdfQuestionView.svelte';
	import { celebrateFullMarks } from '$lib/celebrations';

	// ── Mode toggle ──────────────────────────────────────────────
	let mode: 'revision' | 'practice' = $state('practice');

	// ── Shared state ─────────────────────────────────────────────
	let specs: SpecInfo[] = $state([]);
	let loading: boolean = $state(true);
	let questionKey: number = $state(0);

	// ── My Revision state ────────────────────────────────────────
	let specFilter: string = $state('');
	let questionBatch: RevisionQuestion[] = $state([]);
	let currentQuestion: RevisionQuestion | null = $state(null);
	let totalCount: number = $state(0);
	let specCodes: string[] = $state([]);
	let marksInput: number = $state(0);
	let submitted: boolean = $state(false);
	let submitResult: { success: boolean; is_full_marks: boolean } | null = $state(null);
	let showPdf: boolean = $state(false);
	let fetching: boolean = $state(false);
	let downloading: boolean = $state(false);
	let downloadingMarkScheme: boolean = $state(false);
	let submitting: boolean = $state(false);
	let deleting: boolean = $state(false);

	// ── Quick Practice state ─────────────────────────────────────
	let qpSpecFilter: string = $state('');
	let qpStrandFilter: string = $state('');
	let qpTopicFilter: string = $state('');
	let qpBatch: QuickPracticeQuestion[] = $state([]);
	let qpCurrent: QuickPracticeQuestion | null = $state(null);
	let qpTotal: number = $state(0);
	let qpSpecCodes: string[] = $state([]);
	let qpFilterOptions: Record<string, string[]> = $state({});
	let qpMarksInput: number = $state(0);
	let qpSubmitted: boolean = $state(false);
	let qpFetching: boolean = $state(false);
	let qpDownloadingMs: boolean = $state(false);
	let qpDownloadingPdf: boolean = $state(false);
	let qpShowPdf: boolean = $state(false);

	// ── Custom dropdown state ────────────────────────────────────
	let qpSpecDropdownOpen: boolean = $state(false);
	let qpStrandDropdownOpen: boolean = $state(false);
	let qpTopicDropdownOpen: boolean = $state(false);

	let qpSpecLabel = $derived(
		qpSpecFilter ? specDisplayName(qpSpecFilter) : 'All specs'
	);
	let qpStrandLabel = $derived(
		qpStrandFilter || 'All strands'
	);
	let qpTopicLabel = $derived(
		qpTopicFilter || 'All topics'
	);

	// Click-outside action for closing dropdowns
	function clickOutside(node: HTMLElement, callback: () => void) {
		function handleClick(e: MouseEvent) {
			if (!node.contains(e.target as Node)) callback();
		}
		document.addEventListener('click', handleClick, true);
		return {
			destroy() {
				document.removeEventListener('click', handleClick, true);
			}
		};
	}

	function specDisplayName(code: string): string {
		const spec = specs.find((s) => s.spec_code === code);
		if (spec) return `${spec.exam_board} ${spec.subject}`;
		return code;
	}

	// ── My Revision logic ────────────────────────────────────────
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

	async function handleDownloadMarkScheme() {
		if (!currentQuestion || downloadingMarkScheme) return;
		downloadingMarkScheme = true;
		try {
			const blob = await downloadSessionMarkScheme(currentQuestion.session_id);
			const url = URL.createObjectURL(blob);
			window.open(url, '_blank');
		} catch (e) {
			console.error('Failed to open mark scheme:', e);
		} finally {
			downloadingMarkScheme = false;
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

	// ── Quick Practice logic ─────────────────────────────────────
	function qpTopicDisplay(q: QuickPracticeQuestion): string {
		if (q.predictions.length > 0) {
			const p = q.predictions[0];
			return `${p.spec_sub_section} ${p.subtopic}`;
		}
		return 'Unclassified';
	}

	function qpPickNext() {
		qpSubmitted = false;
		qpMarksInput = 0;
		qpShowPdf = false;
		questionKey++;

		if (qpBatch.length === 0) {
			qpCurrent = null;
			return;
		}

		const idx = Math.floor(Math.random() * qpBatch.length);
		qpCurrent = qpBatch.splice(idx, 1)[0];

		if (qpBatch.length < 3 && !qpFetching) {
			qpRefillBatch();
		}
	}

	async function qpRefillBatch() {
		qpFetching = true;
		try {
			const data = await getQuickPractice(
				qpSpecFilter || undefined,
				qpStrandFilter || undefined,
				qpTopicFilter || undefined,
				20
			);
			// Deduplicate by question_text (cache might return same questions)
			const existingTexts = new Set(qpBatch.map((q) => q.question_text));
			if (qpCurrent) existingTexts.add(qpCurrent.question_text);
			const newQuestions = data.questions.filter((q) => !existingTexts.has(q.question_text));
			qpBatch = [...qpBatch, ...newQuestions];
		} catch (e) {
			console.error('Failed to refill quick practice batch:', e);
		} finally {
			qpFetching = false;
		}
	}

	async function fetchQuickPractice() {
		loading = true;
		try {
			const [data, specList] = await Promise.all([
				getQuickPractice(
					qpSpecFilter || undefined,
					qpStrandFilter || undefined,
					qpTopicFilter || undefined,
					20
				),
				specs.length === 0 ? getSpecs() : Promise.resolve(specs)
			]);
			if (specs.length === 0) specs = specList;
			qpBatch = data.questions;
			qpTotal = data.total_available;
			qpSpecCodes = data.spec_codes;
			qpFilterOptions = data.filter_options;
			qpPickNext();
		} catch (e) {
			console.error('Failed to fetch quick practice:', e);
			qpBatch = [];
			qpCurrent = null;
			qpTotal = 0;
		} finally {
			loading = false;
		}
	}

	function selectQpSpec(value: string) {
		qpSpecFilter = value;
		qpStrandFilter = '';
		qpTopicFilter = '';
		qpSpecDropdownOpen = false;
		qpBatch = [];
		qpCurrent = null;
		fetchQuickPractice();
	}

	function selectQpStrand(value: string) {
		qpStrandFilter = value;
		qpTopicFilter = '';
		qpStrandDropdownOpen = false;
		qpBatch = [];
		qpCurrent = null;
		fetchQuickPractice();
	}

	function selectQpTopic(value: string) {
		qpTopicFilter = value;
		qpTopicDropdownOpen = false;
		qpBatch = [];
		qpCurrent = null;
		fetchQuickPractice();
	}

	function qpHandleSubmit() {
		if (!qpCurrent) return;
		qpSubmitted = true;
		if (qpCurrent.marks_available && qpMarksInput >= qpCurrent.marks_available) {
			celebrateFullMarks();
		}
	}

	async function handleQpDownloadMarkScheme() {
		if (!qpCurrent || qpDownloadingMs) return;
		qpDownloadingMs = true;
		try {
			const blob = await downloadQuickPracticeMarkScheme(qpCurrent.cached_paper_id);
			const url = URL.createObjectURL(blob);
			window.open(url, '_blank');
		} catch (e) {
			console.error('Failed to open mark scheme:', e);
		} finally {
			qpDownloadingMs = false;
		}
	}

	async function handleQpDownloadPdf() {
		if (!qpCurrent || qpDownloadingPdf) return;
		qpDownloadingPdf = true;
		try {
			const blob = await downloadQuickPracticePdf(qpCurrent.cached_paper_id);
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = `${qpCurrent.exam_board}_${qpCurrent.spec_code}.pdf`;
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(url);
		} catch (e) {
			console.error('Failed to download PDF:', e);
		} finally {
			qpDownloadingPdf = false;
		}
	}

	// ── Mode switching ───────────────────────────────────────────
	function switchMode(newMode: 'revision' | 'practice') {
		if (mode === newMode) return;
		mode = newMode;
		loading = true;
		questionKey = 0;
		if (newMode === 'revision') {
			fetchPool(specFilter);
		} else {
			fetchQuickPractice();
		}
	}

	// ── Shared transitions ───────────────────────────────────────
	function throwOut(node: Element, { duration = 400 } = {}) {
		return {
			duration,
			easing: cubicIn,
			css: (t: number) => {
				const angle   = (1 - t) * 20;
				const tx      = (1 - t) * 110;
				const ty      = -(1 - t) * 80;
				const opacity = t < 0.3 ? t / 0.3 : 1;
				return `
					position: absolute;
					width: 100%;
					left: 0;
					top: 0;
					z-index: 10;
					transform: rotate(${angle}deg) translate(${tx}%, ${ty}px);
					opacity: ${opacity};
				`;
			}
		};
	}

	function dealIn(node: Element, { duration = 350 } = {}) {
		return {
			duration,
			easing: cubicOut,
			css: (t: number) => {
				const ty    = (1 - t) * 24;
				const scale = 0.96 + t * 0.04;
				return `
					transform: translateY(${ty}px) scale(${scale});
					opacity: ${t};
				`;
			}
		};
	}

	onMount(() => {
		fetchQuickPractice();
	});
</script>

<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.22/dist/katex.min.css" />

<div class="revision-page">
	<div class="mode-toggle">
		<button
			class="toggle-btn"
			class:active={mode === 'practice'}
			onclick={() => switchMode('practice')}
		>Quick Practice</button>
		<button
			class="toggle-btn"
			class:active={mode === 'revision'}
			onclick={() => switchMode('revision')}
		>My Revision</button>
	</div>

	{#if loading}
		<div class="centered">
			<div class="spinner"></div>
			<p class="muted">Loading questions...</p>
		</div>

	<!-- ═══ QUICK PRACTICE MODE ═══ -->
	{:else if mode === 'practice'}
		{#if !qpCurrent}
			<div class="centered" in:fly={{ y: 20, duration: 300 }}>
				<h2 class="empty-title">No practice questions available</h2>
				<p class="muted">Questions appear here once exam papers have been classified. Try selecting a different spec or topic filter.</p>
			</div>
		{:else}
			<div class="transition-container" in:fly={{ y: 20, duration: 300 }}>
				<div class="stack-wrapper">
					{#if qpBatch.length >= 2}
						<div class="ghost-card ghost-card-2"></div>
					{/if}
					{#if qpBatch.length >= 1}
						<div class="ghost-card ghost-card-1"></div>
					{/if}
					{#key questionKey}
						<div class="revision-content" in:dealIn out:throwOut>
							<div class="top-bar">
								<div class="top-bar-left">
									<span class="spec-badge">{qpCurrent.exam_board || specDisplayName(qpCurrent.spec_code)}</span>
									<span class="meta">Q{qpCurrent.question_number}</span>
									{#if qpCurrent.marks_available}
										<span class="meta-dot">&middot;</span>
										<span class="meta">{qpCurrent.marks_available} mark{qpCurrent.marks_available !== 1 ? 's' : ''}</span>
									{/if}
								</div>
								<div class="top-bar-right">
									<span class="pool-count">{qpTotal} available</span>
								</div>
							</div>

							<div class="question-body">
								{#if qpShowPdf && qpCurrent.pdf_location}
									<PdfQuestionView
										pdfUrl={`/revision/quick-practice/${qpCurrent.cached_paper_id}/pdf`}
										pdfLocation={qpCurrent.pdf_location}
									/>
								{:else}
									<div class="question-text">
										<MathText text={qpCurrent.question_text} />
									</div>
								{/if}
							</div>

							<div class="bottom-controls">
								<div class="actions-row">
									{#if qpCurrent.has_pdf && qpCurrent.pdf_location}
										<button class="action-btn" onclick={() => (qpShowPdf = !qpShowPdf)}>
											{qpShowPdf ? 'View text' : 'View full question'}
										</button>
									{/if}
									<button class="action-btn" onclick={handleQpDownloadPdf} disabled={qpDownloadingPdf || !qpCurrent.has_pdf}>
										{qpDownloadingPdf ? 'Downloading...' : 'Download PDF'}
									</button>
									<button class="action-btn" onclick={handleQpDownloadMarkScheme} disabled={qpDownloadingMs}>
										{qpDownloadingMs ? 'Opening...' : 'View mark scheme'}
									</button>
								</div>
								{#if !qpSubmitted}
									<div class="submit-row" out:slide={{ duration: 200, axis: 'y' }}>
										{#if qpCurrent.marks_available}
											<div class="marks-group">
												<input
													type="number"
													class="marks-input"
													bind:value={qpMarksInput}
													min="0"
													max={qpCurrent.marks_available}
												/>
												<span class="marks-divider">/ {qpCurrent.marks_available} marks</span>
											</div>
										{/if}
										<div class="submit-actions">
											<button class="action-btn" onclick={qpPickNext}>Skip</button>
											<button class="primary-btn" onclick={qpHandleSubmit}>
												Submit
											</button>
										</div>
									</div>
								{:else}
									<div
										class="result-section"
										class:full-marks={qpCurrent.marks_available != null && qpMarksInput >= qpCurrent.marks_available}
										class:partial={qpCurrent.marks_available != null && qpMarksInput < qpCurrent.marks_available}
										in:slide={{ duration: 300, axis: 'y' }}
									>
										<div class="result-banner">
											{#if qpCurrent.marks_available != null && qpMarksInput >= qpCurrent.marks_available}
												<span class="result-icon">&#10003;</span>
												<span>Full marks!</span>
											{:else}
												<span class="result-icon">&#8635;</span>
												<span>Keep practising</span>
											{/if}
										</div>

										<div class="result-details">
											<div class="result-row">
												<span class="detail-label">Topic</span>
												<span class="detail-value">{qpTopicDisplay(qpCurrent)}</span>
											</div>
											{#if qpCurrent.marks_available}
												<div class="result-row">
													<span class="detail-label">Your marks</span>
													<span class="detail-value">{qpMarksInput}/{qpCurrent.marks_available}</span>
												</div>
											{/if}
										</div>

										<button class="primary-btn next-btn" onclick={qpPickNext}>Next Question</button>
									</div>
								{/if}
							</div>
						</div>
					{/key}
				</div>

				<!-- Filters below the card -->
				<div class="qp-filters" in:fly={{ y: 10, duration: 200, delay: 100 }}>
					<!-- Spec dropdown -->
					<div class="custom-select" use:clickOutside={() => (qpSpecDropdownOpen = false)}>
						<button
							type="button"
							class="custom-select-trigger"
							class:open={qpSpecDropdownOpen}
							class:has-value={qpSpecFilter !== ''}
							onclick={() => (qpSpecDropdownOpen = !qpSpecDropdownOpen)}
							aria-haspopup="listbox"
							aria-expanded={qpSpecDropdownOpen}
						>
							<span class="trigger-text" class:placeholder={!qpSpecFilter}>{qpSpecLabel}</span>
							<svg class="chevron" class:rotated={qpSpecDropdownOpen} xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
								<polyline points="6 9 12 15 18 9"/>
							</svg>
						</button>
						{#if qpSpecDropdownOpen}
							<ul class="custom-options" role="listbox" in:fly={{ y: 6, duration: 180, opacity: 0 }} out:fade={{ duration: 120 }}>
								<li role="option" aria-selected={qpSpecFilter === ''}>
									<button type="button" class="option-btn" class:selected={qpSpecFilter === ''} onclick={() => selectQpSpec('')}>
										<span class="option-name">All specs</span>
									</button>
								</li>
								{#if qpSpecCodes.length > 0}
									<li class="option-separator" role="separator"><hr /></li>
								{/if}
								{#each qpSpecCodes as code}
									{@const spec = specs.find(s => s.spec_code === code)}
									<li role="option" aria-selected={qpSpecFilter === code}>
										<button type="button" class="option-btn" class:selected={qpSpecFilter === code} onclick={() => selectQpSpec(code)}>
											{#if spec}
												<span class="option-board">{spec.exam_board}</span>
												<span class="option-name">{spec.subject}</span>
												<span class="option-code">{spec.spec_code}</span>
											{:else}
												<span class="option-name">{code}</span>
											{/if}
										</button>
									</li>
								{/each}
							</ul>
						{/if}
					</div>

					<!-- Strand dropdown -->
					{#if Object.keys(qpFilterOptions).length > 0}
						<div class="custom-select" use:clickOutside={() => (qpStrandDropdownOpen = false)}>
							<button
								type="button"
								class="custom-select-trigger"
								class:open={qpStrandDropdownOpen}
								class:has-value={qpStrandFilter !== ''}
								onclick={() => (qpStrandDropdownOpen = !qpStrandDropdownOpen)}
								aria-haspopup="listbox"
								aria-expanded={qpStrandDropdownOpen}
							>
								<span class="trigger-text" class:placeholder={!qpStrandFilter}>{qpStrandLabel}</span>
								<svg class="chevron" class:rotated={qpStrandDropdownOpen} xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
									<polyline points="6 9 12 15 18 9"/>
								</svg>
							</button>
							{#if qpStrandDropdownOpen}
								<ul class="custom-options" role="listbox" in:fly={{ y: 6, duration: 180, opacity: 0 }} out:fade={{ duration: 120 }}>
									<li role="option" aria-selected={qpStrandFilter === ''}>
										<button type="button" class="option-btn" class:selected={qpStrandFilter === ''} onclick={() => selectQpStrand('')}>
											<span class="option-name">All strands</span>
										</button>
									</li>
									<li class="option-separator" role="separator"><hr /></li>
									{#each Object.keys(qpFilterOptions) as s}
										<li role="option" aria-selected={qpStrandFilter === s}>
											<button type="button" class="option-btn" class:selected={qpStrandFilter === s} onclick={() => selectQpStrand(s)}>
												<span class="option-name">{s}</span>
											</button>
										</li>
									{/each}
								</ul>
							{/if}
						</div>
					{/if}

					<!-- Topic dropdown -->
					{#if qpStrandFilter && qpFilterOptions[qpStrandFilter]?.length > 0}
						<div class="custom-select" use:clickOutside={() => (qpTopicDropdownOpen = false)}>
							<button
								type="button"
								class="custom-select-trigger"
								class:open={qpTopicDropdownOpen}
								class:has-value={qpTopicFilter !== ''}
								onclick={() => (qpTopicDropdownOpen = !qpTopicDropdownOpen)}
								aria-haspopup="listbox"
								aria-expanded={qpTopicDropdownOpen}
							>
								<span class="trigger-text" class:placeholder={!qpTopicFilter}>{qpTopicLabel}</span>
								<svg class="chevron" class:rotated={qpTopicDropdownOpen} xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
									<polyline points="6 9 12 15 18 9"/>
								</svg>
							</button>
							{#if qpTopicDropdownOpen}
								<ul class="custom-options" role="listbox" in:fly={{ y: 6, duration: 180, opacity: 0 }} out:fade={{ duration: 120 }}>
									<li role="option" aria-selected={qpTopicFilter === ''}>
										<button type="button" class="option-btn" class:selected={qpTopicFilter === ''} onclick={() => selectQpTopic('')}>
											<span class="option-name">All topics</span>
										</button>
									</li>
									<li class="option-separator" role="separator"><hr /></li>
									{#each qpFilterOptions[qpStrandFilter] as t}
										<li role="option" aria-selected={qpTopicFilter === t}>
											<button type="button" class="option-btn" class:selected={qpTopicFilter === t} onclick={() => selectQpTopic(t)}>
												<span class="option-name">{t}</span>
											</button>
										</li>
									{/each}
								</ul>
							{/if}
						</div>
					{/if}
				</div>
			</div>
		{/if}

	<!-- ═══ MY REVISION MODE ═══ -->
	{:else if !currentQuestion}
		<div class="centered" in:fly={{ y: 20, duration: 300 }}>
			<div class="empty-icon">&#10003;</div>
			<h2 class="empty-title">No questions available</h2>
			<p class="muted">Questions appear here when you've scored below full marks on a session. Mark some exam sessions to build your revision pool.</p>
		</div>
	{:else}
		<div class="transition-container" in:fly={{ y: 20, duration: 300 }}>
			<div class="stack-wrapper">
				{#if questionBatch.length >= 2}
					<div class="ghost-card ghost-card-2"></div>
				{/if}
				{#if questionBatch.length >= 1}
					<div class="ghost-card ghost-card-1"></div>
				{/if}
				{#key questionKey}
					<div class="revision-content" in:dealIn out:throwOut>
						<div class="top-bar">
							<div class="top-bar-left">
								<span class="spec-badge">{specDisplayName(currentQuestion.spec_code)}</span>
								<span class="meta">Q{currentQuestion.question_number}</span>
								<span class="meta-dot">&middot;</span>
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
								<button class="action-btn" onclick={handleDownloadMarkScheme} disabled={downloadingMarkScheme || !currentQuestion.has_mark_scheme}>
									{downloadingMarkScheme ? 'Opening...' : 'View mark scheme'}
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
		</div>
	{/if}
</div>

<style>
	.mode-toggle {
		display: flex;
		gap: 4px;
		background: var(--color-surface-alt);
		border-radius: var(--radius-md);
		padding: 3px;
		margin-bottom: 20px;
		width: fit-content;
	}

	.toggle-btn {
		padding: 7px 16px;
		border: none;
		border-radius: var(--radius-sm);
		font-size: 0.84rem;
		font-weight: 600;
		cursor: pointer;
		background: transparent;
		color: var(--color-text-muted);
		transition: background var(--transition-fast), color var(--transition-fast);
		font-family: var(--font-body);
		white-space: nowrap;
	}

	.toggle-btn.active {
		background: var(--color-surface);
		color: var(--color-text);
		box-shadow: var(--shadow-sm);
	}

	.toggle-btn:hover:not(.active) {
		color: var(--color-text-secondary);
	}

	.qp-filters {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
		margin-top: 16px;
	}

	.transition-container {
		display: grid;
		grid-template-columns: 1fr;
		width: 100%;
	}

	.stack-wrapper {
		position: relative;
		width: 100%;
		padding-bottom: 14px;
		grid-column: 1;
		grid-row: 1;
	}

	.ghost-card {
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: var(--color-surface);
		border-radius: var(--radius-lg);
		border: 1.5px solid var(--color-border);
		pointer-events: none;
	}

	.ghost-card-1 {
		transform: translateY(6px) scaleX(0.97);
		transform-origin: top center;
		z-index: 1;
		opacity: 0.85;
	}

	.ghost-card-2 {
		transform: translateY(12px) scaleX(0.94);
		transform-origin: top center;
		z-index: 0;
		opacity: 0.7;
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

		position: relative;
		z-index: 2;
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

	/* Custom dropdown styles */
	.custom-select {
		position: relative;
		display: block;
		flex: 1;
		min-width: 140px;
	}

	.custom-select-trigger {
		display: flex;
		align-items: center;
		justify-content: space-between;
		width: 100%;
		padding: 8px 12px;
		background: var(--color-surface);
		border: 1.5px solid var(--color-border);
		border-radius: var(--radius-sm);
		font-size: 0.85rem;
		font-family: var(--font-body);
		color: var(--color-text);
		cursor: pointer;
		box-shadow: var(--shadow-sm);
		text-align: left;
		gap: 8px;
		transition:
			border-color var(--transition-fast),
			box-shadow var(--transition-fast),
			background var(--transition-fast);
	}

	.custom-select-trigger:hover:not(:disabled) {
		border-color: var(--color-border-hover);
	}

	.custom-select-trigger:focus {
		outline: none;
		border-color: var(--color-primary);
		box-shadow: 0 0 0 3px var(--color-primary-glow);
	}

	.custom-select-trigger.open {
		border-color: var(--color-primary);
		box-shadow: 0 0 0 3px var(--color-primary-glow);
	}

	.trigger-text {
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		min-width: 0;
	}

	.trigger-text.placeholder {
		color: var(--color-text-muted);
	}

	.chevron {
		flex-shrink: 0;
		color: var(--color-text-muted);
		transition: transform 220ms cubic-bezier(0.4, 0, 0.2, 1), color var(--transition-fast);
	}

	.chevron.rotated {
		transform: rotate(180deg);
		color: var(--color-primary);
	}

	.custom-options {
		position: absolute;
		bottom: calc(100% + 6px);
		left: 0;
		right: 0;
		z-index: 50;
		background: var(--color-surface);
		border: 1.5px solid var(--color-border);
		border-radius: var(--radius-sm);
		box-shadow: var(--shadow-md), 0 8px 24px rgba(0, 0, 0, 0.08);
		list-style: none;
		margin: 0;
		padding: 4px;
		max-height: 280px;
		overflow-y: auto;
		overscroll-behavior: contain;
		scrollbar-width: thin;
		scrollbar-color: var(--color-border) transparent;
	}

	.custom-options::-webkit-scrollbar {
		width: 6px;
	}

	.custom-options::-webkit-scrollbar-track {
		background: transparent;
	}

	.custom-options::-webkit-scrollbar-thumb {
		background: var(--color-border);
		border-radius: 3px;
	}

	.custom-options::-webkit-scrollbar-thumb:hover {
		background: var(--color-text-muted);
	}

	.option-btn {
		display: flex;
		align-items: center;
		gap: 10px;
		width: 100%;
		padding: 9px 10px;
		background: transparent;
		border: none;
		border-radius: calc(var(--radius-sm) - 2px);
		font-family: var(--font-body);
		font-size: 0.85rem;
		color: var(--color-text);
		cursor: pointer;
		text-align: left;
		transition: background var(--transition-fast), color var(--transition-fast);
	}

	.option-btn:hover {
		background: var(--color-surface-alt);
	}

	.option-btn.selected {
		background: var(--color-primary-light);
		color: var(--color-primary);
		font-weight: 600;
	}

	.option-separator {
		list-style: none;
		padding: 2px 10px;
	}

	.option-separator hr {
		border: none;
		border-top: 1px solid var(--color-border);
		margin: 0;
	}

	.option-board {
		font-size: 0.7rem;
		font-weight: 700;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		color: var(--color-primary);
		background: var(--color-primary-light);
		padding: 2px 6px;
		border-radius: 4px;
		flex-shrink: 0;
	}

	.option-name {
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.option-code {
		font-size: 0.75rem;
		color: var(--color-text-muted);
		font-weight: 500;
		flex-shrink: 0;
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

		.qp-filters {
			flex-direction: column;
		}

		.qp-filters .custom-select {
			width: 100%;
		}
	}
</style>
