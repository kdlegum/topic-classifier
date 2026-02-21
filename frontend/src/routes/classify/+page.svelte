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
	import { shouldAnimate, DURATIONS } from '$lib/motion';

	let specCode = $state('None');
	let questions = $state(['']);
	let isSubmitting = $state(false);
	let isUploading = $state(false);
	let pdfStatus = $state('');
	let ready = $state(false);
	let selectedFileName = $state('');
	let hasMath = $state(false);

	let allSpecs: SpecInfo[] = $state([]);
	let specsLoading = $state(true);

	// Dropdown state
	let dropdownOpen = $state(false);

	// Strand state
	let selectedModules: string[] = $state([]);
	let paperStrands: string[] = $state([]);
	let moduleSaveTimeout: ReturnType<typeof setTimeout> | null = null;
	let modulesLoadedForSpec: string | null = $state(null);

	// Derived from selected spec
	let currentSpec = $derived(allSpecs.find((s) => s.spec_code === specCode) ?? null);
	let selectedSpecLabel = $derived(
		currentSpec
			? `${currentSpec.exam_board} ${currentSpec.qualification} ${currentSpec.subject} (${currentSpec.spec_code})`
			: 'No specification'
	);

	let fileInput: HTMLInputElement;

	// Click-outside action for closing the dropdown
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
		hasMath = false;

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

		isSubmitting = true;

		try {
			const apiSpecCode = specCode === 'None' ? null : specCode;
			const strands = specCode === 'None' ? undefined : getEffectiveStrands();
			const data = await classifyQuestions(filled, apiSpecCode, strands);
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

		isUploading = true;
		pdfStatus = 'Uploading...';

		try {
			const uploadSpecCode = specCode === 'None' ? 'NONE' : specCode;
			const strands = specCode === 'None' ? undefined : getEffectiveStrands();
			const data = await uploadPdf(file, uploadSpecCode, strands, hasMath);
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

	function handleFileChange(e: Event) {
		const input = e.target as HTMLInputElement;
		selectedFileName = input.files?.[0]?.name ?? '';
	}

	function selectSpec(code: string) {
		specCode = code;
		dropdownOpen = false;
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
			<p class="page-subtitle">Upload your question paper or paste questions to get a topic breakdown.</p>
		</div>

		<!-- Specification selection -->
		<div class="section" in:fly={{ y: 20, duration: 300, delay: 50 }}>
			<label>Specification</label>
			{#if specsLoading}
				<div class="custom-select" aria-disabled="true">
					<button type="button" class="custom-select-trigger" disabled>
						<span class="trigger-text muted">Loading specifications...</span>
						<svg class="chevron" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
							<polyline points="6 9 12 15 18 9"/>
						</svg>
					</button>
				</div>
			{:else}
				<div
					class="custom-select"
					use:clickOutside={() => (dropdownOpen = false)}
				>
					<button
						type="button"
						class="custom-select-trigger"
						class:open={dropdownOpen}
						class:has-value={specCode !== 'None'}
						onclick={() => (dropdownOpen = !dropdownOpen)}
						aria-haspopup="listbox"
						aria-expanded={dropdownOpen}
					>
						<span class="trigger-text" class:placeholder={specCode === 'None'}>
							{selectedSpecLabel}
						</span>
						<svg class="chevron" class:rotated={dropdownOpen} xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
							<polyline points="6 9 12 15 18 9"/>
						</svg>
					</button>

					{#if dropdownOpen}
						<ul
							class="custom-options"
							role="listbox"
							in:fly={{ y: -6, duration: 180, opacity: 0 }}
							out:fade={{ duration: 120 }}
						>
							<li role="option" aria-selected={specCode === 'None'}>
								<button
									type="button"
									class="option-btn"
									class:selected={specCode === 'None'}
									onclick={() => selectSpec('None')}
								>
									<span class="option-name option-no-spec">No specification</span>
									<span class="option-code">unclassified</span>
								</button>
							</li>
							{#if allSpecs.length > 0}
								<li class="option-separator" role="separator"><hr /></li>
							{/if}
							{#each allSpecs as spec}
								<li role="option" aria-selected={specCode === spec.spec_code}>
									<button
										type="button"
										class="option-btn"
										class:selected={specCode === spec.spec_code}
										onclick={() => selectSpec(spec.spec_code)}
									>
										<span class="option-board">{spec.exam_board}</span>
										<span class="option-name">{spec.qualification} {spec.subject}</span>
										<span class="option-code">{spec.spec_code}</span>
									</button>
								</li>
							{/each}
							{#if allSpecs.length === 0}
								<li class="option-empty">
									<a href="/specs" onclick={() => (dropdownOpen = false)}>Browse and add specifications</a>
								</li>
							{/if}
						</ul>
					{/if}
				</div>
			{/if}
		</div>

		<!-- Math checkbox for no-spec sessions -->
		<div in:fly={{ y: 20, duration: 300, delay: 75 }}>
			{#if specCode === 'None'}
				<div class="section">
					<label class="checkbox-label">
						<input type="checkbox" bind:checked={hasMath} />
						<span>Does this paper contain math notation?</span>
					</label>
					<p class="section-hint">Enables a math-optimised OCR pipeline for PDF uploads.</p>
				</div>
			{/if}
		</div>

		<!-- Module selection for optional_modules specs -->
		{#if currentSpec?.optional_modules}
			<div class="section" in:fly={{ y: 20, duration: 300, delay: 75 }}>
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
			<div class="section" in:fly={{ y: 20, duration: 300, delay: 75 }}>
				<StrandPicker
					strands={currentSpec.strands}
					bind:selected={paperStrands}
					label="Paper Strands (optional)"
					hint="Narrow classification to specific strands for this paper. Leave blank for all strands."
				/>
			</div>
		{/if}

		<!-- PDF Upload -->
		<div class="section" in:fly={{ y: 20, duration: 300, delay: 100 }}>
			<label>Upload Question Paper (PDF)</label>
			<div class="pdf-upload-area">
				<input
					type="file"
					id="pdf-upload"
					accept="application/pdf"
					bind:this={fileInput}
					onchange={handleFileChange}
					class="file-input-hidden"
				/>
				<label for="pdf-upload" class="file-input-label" class:file-selected={!!selectedFileName}>
					<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
						<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
						<polyline points="17 8 12 3 7 8"/>
						<line x1="12" y1="3" x2="12" y2="15"/>
					</svg>
					<span class="file-label-text">{selectedFileName || 'Choose PDF file'}</span>
				</label>
				<button type="button" class="btn-upload" onclick={handlePdfUpload} disabled={isUploading}>
					{isUploading ? 'Processing...' : 'Upload & Extract'}
				</button>
			</div>
			{#if pdfStatus}
				<div class="pdf-status" in:fade={{ duration: 200 }}>
					{#if isUploading}
						<span class="pdf-spinner"></span>
					{/if}
					{pdfStatus}
				</div>
			{/if}
		</div>

		<!-- Divider -->
		<div class="section-divider" in:fade={{ duration: 200, delay: 120 }}>
			<span>or enter questions manually</span>
		</div>

		<!-- Questions -->
		<div class="section" in:fly={{ y: 20, duration: 300, delay: 150 }}>
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
				{isSubmitting ? 'Saving...' : specCode === 'None' ? 'Save questions (no classification)' : 'Submit all questions'}
			</button>
		</div>
	{/if}
</main>

<style>
	.page-subtitle {
		color: var(--color-text-secondary);
		font-size: 1.02rem;
		margin-bottom: 8px;
	}

	/* ─── Custom Animated Select ─── */
	.custom-select {
		position: relative;
		display: block;
	}

	.custom-select-trigger {
		display: flex;
		align-items: center;
		justify-content: space-between;
		width: 100%;
		padding: 11px 14px;
		background: var(--color-surface);
		border: 1.5px solid var(--color-border);
		border-radius: var(--radius-sm);
		font-size: 1rem;
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

	.custom-select-trigger:disabled {
		background: var(--color-surface-alt);
		color: var(--color-text-muted);
		cursor: not-allowed;
	}

	.trigger-text {
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		min-width: 0;
	}

	.trigger-text.placeholder,
	.muted {
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

	/* Options panel */
	.custom-options {
		position: absolute;
		top: calc(100% + 6px);
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
		font-size: 0.93rem;
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

	.option-empty {
		padding: 8px 10px;
		font-size: 0.88rem;
		color: var(--color-text-muted);
		list-style: none;
	}

	.option-no-spec {
		font-style: italic;
		color: var(--color-text-secondary);
	}

	.option-board {
		font-size: 0.75rem;
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
		font-size: 0.8rem;
		color: var(--color-text-muted);
		font-weight: 500;
		flex-shrink: 0;
	}

	/* ─── Math checkbox ─── */
	.checkbox-label {
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: 0.95rem;
		cursor: pointer;
		margin-bottom: 4px;
		font-weight: 500;
	}

	.checkbox-label input[type='checkbox'] {
		appearance: none;
		-webkit-appearance: none;
		width: 17px;
		height: 17px;
		flex-shrink: 0;
		margin: 0;
		cursor: pointer;
		border: 1.5px solid var(--color-border);
		border-radius: 4px;
		background: var(--color-surface);
		transition:
			border-color var(--transition-fast),
			background var(--transition-fast),
			box-shadow var(--transition-fast);
	}

	.checkbox-label input[type='checkbox']:checked {
		border-color: var(--color-primary);
		background: var(--color-primary);
		background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 10 10'%3E%3Cpolyline points='1.5 5 4 7.5 8.5 2' fill='none' stroke='white' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
		background-repeat: no-repeat;
		background-position: center;
	}

	.checkbox-label input[type='checkbox']:focus-visible {
		outline: none;
		border-color: var(--color-primary);
		box-shadow: 0 0 0 3px var(--color-primary-glow);
	}

	.section-hint {
		font-size: 0.82rem;
		color: var(--color-text-muted);
		margin: 0;
	}

	/* ─── PDF Upload Area ─── */
	.pdf-upload-area {
		display: flex;
		gap: 10px;
		align-items: stretch;
		flex-wrap: wrap;
	}

	/* Visually hide the native file input while keeping it accessible */
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

	.file-input-label {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		flex: 1;
		min-width: 160px;
		padding: 10px 16px;
		margin-bottom: 0;
		background: var(--color-surface);
		border: 1.5px solid var(--color-border);
		border-radius: var(--radius-sm);
		font-size: 0.95rem;
		font-family: var(--font-body);
		font-weight: 500;
		color: var(--color-text-secondary);
		cursor: pointer;
		box-shadow: var(--shadow-sm);
		transition:
			border-color var(--transition-normal),
			color var(--transition-normal),
			background var(--transition-normal),
			box-shadow var(--transition-normal);
		overflow: hidden;
	}

	.file-input-label:hover {
		border-color: var(--color-primary);
		color: var(--color-text);
		background: var(--color-primary-light);
	}

	.file-input-label.file-selected {
		border-color: var(--color-primary);
		color: var(--color-text);
		background: var(--color-primary-light);
	}

	.file-input-label svg {
		flex-shrink: 0;
		opacity: 0.65;
	}

	.file-label-text {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		min-width: 0;
	}

	/* ─── Upload Button ─── */
	.btn-upload {
		background: var(--color-surface);
		color: var(--color-text);
		border: 1.5px solid var(--color-border);
		padding: 10px 22px;
		border-radius: var(--radius-sm);
		font-weight: 600;
		font-size: 0.95rem;
		white-space: nowrap;
		width: auto;
		box-shadow: var(--shadow-sm);
		transition:
			background var(--transition-normal),
			border-color var(--transition-normal),
			color var(--transition-normal),
			box-shadow var(--transition-normal),
			transform var(--transition-fast);
	}

	.btn-upload:hover:not(:disabled) {
		background: var(--color-primary);
		border-color: var(--color-primary);
		color: #fff;
		box-shadow: var(--shadow-md);
	}

	.btn-upload:active:not(:disabled) {
		transform: scale(0.97);
	}

	.btn-upload:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	/* ─── Section Divider ─── */
	.section-divider {
		display: flex;
		align-items: center;
		gap: 14px;
		margin: 4px 0;
	}

	.section-divider::before,
	.section-divider::after {
		content: '';
		flex: 1;
		height: 1px;
		background: var(--color-border);
	}

	.section-divider span {
		color: var(--color-text-muted);
		font-size: 0.83rem;
		font-weight: 500;
		white-space: nowrap;
		letter-spacing: 0.01em;
	}

	/* ─── PDF Status ─── */
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
