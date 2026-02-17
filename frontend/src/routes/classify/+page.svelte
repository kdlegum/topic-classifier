<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { fly, fade } from 'svelte/transition';
	import {
		classifyQuestions,
		uploadPdf,
		getPdfStatus,
		getUserSpecs,
		getUserModules,
		saveUserModules,
		type SpecInfo
	} from '$lib/api';
	import StrandPicker from '$lib/components/StrandPicker.svelte';
	import { celebrateCompletion } from '$lib/celebrations';
	import { shouldAnimate, DURATIONS } from '$lib/motion';

	let specCode = $state('None');
	let questions = $state(['']);
	let isSubmitting = $state(false);
	let isUploading = $state(false);
	let pdfStatus = $state('');
	let ready = $state(false);

	let allSpecs: SpecInfo[] = $state([]);
	let specsLoading = $state(true);

	// Strand state
	let selectedModules: string[] = $state([]);
	let paperStrands: string[] = $state([]);
	let moduleSaveTimeout: ReturnType<typeof setTimeout> | null = null;
	let modulesLoadedForSpec: string | null = $state(null);

	// Derived from selected spec
	let currentSpec = $derived(allSpecs.find((s) => s.spec_code === specCode) ?? null);

	let fileInput: HTMLInputElement;

	onMount(async () => {
		try {
			allSpecs = await getUserSpecs();
		} catch (e) {
			console.error('Failed to load specs:', e);
		} finally {
			specsLoading = false;
			ready = true;
		}
	});

	// When spec changes, load module selections if optional_modules
	$effect(() => {
		const spec = currentSpec;
		// Reset strand selections when spec changes
		paperStrands = [];
		selectedModules = [];
		modulesLoadedForSpec = null;

		if (spec?.optional_modules) {
			getUserModules(spec.spec_code)
				.then((data) => {
					selectedModules = data.selected_strands;
					modulesLoadedForSpec = spec.spec_code;
				})
				.catch((e) => {
					console.error('Failed to load user modules:', e);
					modulesLoadedForSpec = spec.spec_code;
				});
		}
	});

	// Auto-save module selections with debounce (only after initial load)
	$effect(() => {
		const modules = selectedModules;
		if (!currentSpec?.optional_modules) return;
		if (modulesLoadedForSpec !== currentSpec.spec_code) return;

		if (moduleSaveTimeout) clearTimeout(moduleSaveTimeout);
		moduleSaveTimeout = setTimeout(() => {
			saveUserModules(currentSpec!.spec_code, modules).catch((e) =>
				console.error('Failed to save modules:', e)
			);
		}, 500);
	});

	function addQuestion() {
		questions = [...questions, ''];
	}

	// Effective strands to pass to API: paper strands take priority, else nothing (let backend resolve)
	function getEffectiveStrands(): string[] | undefined {
		if (paperStrands.length > 0) return paperStrands;
		return undefined;
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
			const data = await classifyQuestions(filled, specCode, getEffectiveStrands());
			celebrateCompletion();
			setTimeout(() => goto(`/mark_session/${data.session_id}`), 1000);
		} catch (error) {
			console.error('Error submitting questions:', error);
			alert('There was an error sending your questions. See console for details.');
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
			const data = await uploadPdf(file, specCode, getEffectiveStrands());
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

					celebrateCompletion();
					setTimeout(() => goto(`/mark_session/${data.session_id}`), 1000);
				}

				if (data.status === 'failed' || data.status.startsWith('Error')) {
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

	function staggerDelay(i: number): number {
		return shouldAnimate() ? i * DURATIONS.stagger : 0;
	}
</script>

<svelte:head>
	<title>Classify - Topic Tracker</title>
</svelte:head>

<main class="page-content">
	{#if ready}
		<div in:fly={{ y: 20, duration: 300 }}>
			<h1>Exam Question Classifier</h1>
			<p class="page-subtitle">Paste your exam questions below or upload an empty question paper and get a topic breakdown.</p>
		</div>

		<!-- Specification selection -->
		<div class="section" in:fly={{ y: 20, duration: 300, delay: 50 }}>
			<label for="specification">Specification</label>
			{#if specsLoading}
				<select id="specification" disabled>
					<option>Loading specifications...</option>
				</select>
			{:else if allSpecs.length === 0}
				<div class="empty-state">
					<p>You haven't added any specifications yet.</p>
					<p><a href="/specs">Browse and add specifications</a> to get started.</p>
				</div>
			{:else}
				<select id="specification" bind:value={specCode}>
					<option value="None">---Choose a Specification---</option>
					{#each allSpecs as spec}
						<option value={spec.spec_code}>
							{spec.exam_board} {spec.qualification} {spec.subject} ({spec.spec_code})
						</option>
					{/each}
				</select>
			{/if}
		</div>

		<!-- Module selection for optional_modules specs -->
		{#if currentSpec?.optional_modules}
			<div class="section" in:fly={{ y: 15, duration: 250 }}>
				<StrandPicker
					strands={currentSpec.strands}
					bind:selected={selectedModules}
					label="Your Modules"
					hint="Select the modules you are studying. These are saved to your account."
				/>
			</div>
		{/if}

		<!-- Paper strand selection for specs with multiple strands -->
		{#if currentSpec && currentSpec.strands.length > 1}
			<div class="section" in:fly={{ y: 15, duration: 250 }}>
				<StrandPicker
					strands={currentSpec.strands}
					bind:selected={paperStrands}
					label="Paper Strands (optional)"
					hint="Narrow classification to specific strands for this paper. Leave blank for all strands."
				/>
			</div>
		{/if}

		<!-- Questions -->
		<div class="section" in:fly={{ y: 20, duration: 300, delay: 100 }}>
			<label for="question-text-field">Questions</label>

			{#each questions as question, i}
				<div class="question" in:fly={{ y: 15, duration: 250, delay: staggerDelay(i) }}>
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
		<div class="section" in:fly={{ y: 20, duration: 300, delay: 150 }}>
			<label for="pdf-upload">Or upload an empty question paper (PDF)</label>
			<input type="file" id="pdf-upload" accept="application/pdf" bind:this={fileInput} />
			<button type="button" class="btn-upload" onclick={handlePdfUpload} disabled={isUploading}>
				{isUploading ? 'Processing...' : 'Upload PDF'}
			</button>
			{#if pdfStatus}
				<div class="pdf-status" in:fade={{ duration: 200 }}>
					{#if isUploading}
						<span class="pdf-spinner"></span>
					{/if}
					{pdfStatus}
				</div>
			{/if}
		</div>
	{/if}
</main>

<style>
	.page-subtitle {
		color: var(--color-text-secondary);
		font-size: 1.02rem;
		margin-bottom: 8px;
	}

	.btn-upload {
		background: var(--color-surface);
		color: var(--color-text);
		border: 1.5px solid var(--color-border);
		padding: 10px 20px;
		border-radius: var(--radius-sm);
		font-weight: 600;
	}

	.btn-upload:hover:not(:disabled) {
		border-color: var(--color-primary);
		color: var(--color-primary);
	}

	.btn-upload:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.pdf-spinner {
		display: inline-block;
		width: 14px;
		height: 14px;
		border: 2px solid var(--color-border);
		border-top-color: var(--color-primary);
		border-radius: 50%;
		animation: spin 0.7s linear infinite;
		vertical-align: middle;
		margin-right: 6px;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}
</style>
