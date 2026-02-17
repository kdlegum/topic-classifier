<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { fly, fade } from 'svelte/transition';
	import { getSpecs, addUserSpec, removeUserSpec, deleteSpec, type SpecInfo } from '$lib/api';
	import { shouldAnimate, DURATIONS } from '$lib/motion';

	let allSpecs: SpecInfo[] = $state([]);
	let loading = $state(true);
	let error = $state(false);
	let ready = $state(false);

	// Search & filters
	let searchQuery = $state('');
	let filterBoard = $state('');
	let filterQualification = $state('');

	let uniqueBoards = $derived([...new Set(allSpecs.map((s) => s.exam_board))].sort());
	let uniqueQualifications = $derived([...new Set(allSpecs.map((s) => s.qualification))].sort());

	let filteredSpecs = $derived(
		allSpecs.filter((s) => {
			const q = searchQuery.toLowerCase();
			const matchesSearch =
				!q ||
				s.subject.toLowerCase().includes(q) ||
				s.spec_code.toLowerCase().includes(q) ||
				s.exam_board.toLowerCase().includes(q) ||
				(s.description ?? '').toLowerCase().includes(q);
			const matchesBoard = !filterBoard || s.exam_board === filterBoard;
			const matchesQual = !filterQualification || s.qualification === filterQualification;
			return matchesSearch && matchesBoard && matchesQual;
		})
	);

	onMount(async () => {
		try {
			allSpecs = await getSpecs();
		} catch (e) {
			console.error('Failed to load specs:', e);
			error = true;
		} finally {
			loading = false;
			ready = true;
		}
	});

	async function toggleSpec(e: Event, spec: SpecInfo) {
		e.preventDefault();
		e.stopPropagation();
		const wasSelected = spec.is_selected;
		// Optimistic update
		spec.is_selected = !wasSelected;
		allSpecs = allSpecs;

		try {
			if (wasSelected) {
				await removeUserSpec(spec.spec_code);
			} else {
				await addUserSpec(spec.spec_code);
			}
		} catch (err) {
			console.error('Failed to toggle spec:', err);
			spec.is_selected = wasSelected;
			allSpecs = allSpecs;
		}
	}

	async function handleDelete(e: Event, spec: SpecInfo) {
		e.preventDefault();
		e.stopPropagation();
		if (!confirm(`Delete "${spec.subject}" (${spec.spec_code})? This cannot be undone.`)) return;
		try {
			await deleteSpec(spec.spec_code);
			allSpecs = allSpecs.filter((s) => s.spec_code !== spec.spec_code);
		} catch (err) {
			console.error('Failed to delete spec:', err);
			alert('Failed to delete specification. It may have sessions referencing it.');
		}
	}

	function staggerDelay(i: number): number {
		return shouldAnimate() ? i * 30 : 0;
	}
</script>

<svelte:head>
	<title>Specifications - Topic Tracker</title>
</svelte:head>

<main class="page-content specs-page">
	{#if ready}
		<div class="specs-header" in:fly={{ y: 20, duration: 300 }}>
			<div>
				<h1>Specifications</h1>
				<p>Browse all specifications and choose which ones you study.</p>
			</div>
			<a href="/specs/create" class="btn-create">Create Specification</a>
		</div>
	{/if}

	{#if loading}
		<div class="loading">
			<span class="loading-spinner"></span>
			Loading specifications...
		</div>
	{:else if error}
		<div class="error-state" in:fade={{ duration: 200 }}>
			<p>Failed to load specifications. Please try again.</p>
		</div>
	{:else}
		<!-- Search & filters -->
		<div class="filters" in:fly={{ y: 15, duration: 250, delay: 50 }}>
			<input
				type="text"
				placeholder="Search by subject, spec code, or exam board..."
				bind:value={searchQuery}
				class="search-input"
			/>
			<div class="filter-row">
				<select bind:value={filterBoard}>
					<option value="">All Exam Boards</option>
					{#each uniqueBoards as board}
						<option value={board}>{board}</option>
					{/each}
				</select>
				<select bind:value={filterQualification}>
					<option value="">All Qualifications</option>
					{#each uniqueQualifications as qual}
						<option value={qual}>{qual}</option>
					{/each}
				</select>
			</div>
		</div>

		{#if filteredSpecs.length === 0}
			<div class="empty-state" in:fade={{ duration: 200 }}>
				<p>No specifications match your search.</p>
			</div>
		{:else}
			<div class="spec-grid">
				{#each filteredSpecs as spec, i (spec.spec_code)}
					<a
						class="spec-card"
						class:selected={spec.is_selected}
						href="/specs/{spec.spec_code}"
						in:fly={{ y: 15, duration: 250, delay: staggerDelay(i) }}
					>
						<div class="spec-card-body">
							<div class="spec-card-top">
								<h3 class="spec-subject">{spec.subject}</h3>
								<div class="spec-badges">
									{#if spec.is_reviewed}
										<span class="badge reviewed">Reviewed</span>
									{/if}
								</div>
							</div>
							<div class="spec-details">
								<span class="spec-board">{spec.exam_board}</span>
								<span class="spec-qual">{spec.qualification}</span>
								<span class="spec-code">{spec.spec_code}</span>
							</div>
							{#if spec.description}
								<p class="spec-description">{spec.description}</p>
							{/if}
							{#if spec.topic_count != null}
								<div class="spec-count">{spec.topic_count} subtopic{spec.topic_count !== 1 ? 's' : ''}</div>
							{/if}
						</div>
						<div class="spec-card-actions">
							<button
								class="btn-toggle"
								class:active={spec.is_selected}
								onclick={(e) => toggleSpec(e, spec)}
							>
								{spec.is_selected ? 'Remove' : 'Add'}
							</button>
							{#if spec.creator_id && !spec.is_reviewed}
								<button class="btn-edit-spec" onclick={(e) => { e.preventDefault(); e.stopPropagation(); goto(`/specs/${spec.spec_code}/edit`); }} title="Edit specification">
									<svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
										<path d="M12.146.146a.5.5 0 0 1 .708 0l3 3a.5.5 0 0 1 0 .708l-10 10a.5.5 0 0 1-.168.11l-5 2a.5.5 0 0 1-.65-.65l2-5a.5.5 0 0 1 .11-.168l10-10zM11.207 2.5 13.5 4.793 14.793 3.5 12.5 1.207 11.207 2.5zm1.586 3L10.5 3.207 4 9.707V10h.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.5h.293l6.5-6.5zm-9.761 5.175-.106.106-1.528 3.821 3.821-1.528.106-.106A.5.5 0 0 1 5 12.5V12h-.5a.5.5 0 0 1-.5-.5V11h-.5a.5.5 0 0 1-.468-.325z"/>
									</svg>
								</button>
								<button class="btn-delete-spec" onclick={(e) => handleDelete(e, spec)} title="Delete specification">
									<svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
										<path d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0V6z"/>
										<path fill-rule="evenodd" d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H5.5l1-1h3l1 1H13a1 1 0 0 1 1 1v1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4H4.118zM2.5 3V2h11v1h-11z"/>
									</svg>
								</button>
							{/if}
						</div>
					</a>
				{/each}
			</div>
		{/if}
	{/if}
</main>

<style>
	.specs-page {
		max-width: 900px;
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

	.specs-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 16px;
		margin-bottom: 24px;
	}

	.specs-header p {
		color: var(--color-text-secondary);
		margin: 4px 0 0;
	}

	.btn-create {
		display: inline-block;
		padding: 10px 20px;
		background: var(--color-primary);
		color: white;
		text-decoration: none;
		border-radius: var(--radius-md);
		font-size: 0.95rem;
		font-weight: 600;
		white-space: nowrap;
		transition: background var(--transition-fast), box-shadow var(--transition-fast);
	}

	.btn-create:hover {
		background: var(--color-primary-hover);
		box-shadow: var(--shadow-md);
	}

	.filters {
		margin-bottom: 24px;
	}

	.search-input {
		width: 100%;
		padding: 10px 14px;
		font-size: 1rem;
		font-family: var(--font-body);
		border: 1.5px solid var(--color-border);
		border-radius: var(--radius-sm);
		margin-bottom: 10px;
		background: var(--color-surface);
		transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
	}

	.search-input:focus {
		outline: none;
		border-color: var(--color-primary);
		box-shadow: 0 0 0 3px var(--color-primary-glow);
	}

	.filter-row {
		display: flex;
		gap: 10px;
	}

	.filter-row select {
		flex: 1;
		padding: 8px 10px;
		font-size: 0.9rem;
		font-family: var(--font-body);
		border: 1.5px solid var(--color-border);
		border-radius: var(--radius-sm);
		background: var(--color-surface);
	}

	.spec-grid {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.spec-card {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 16px 20px;
		border: 1.5px solid var(--color-border);
		border-radius: var(--radius-lg);
		background: var(--color-surface);
		box-shadow: var(--shadow-sm);
		transition: border-color var(--transition-fast), background var(--transition-fast), box-shadow var(--transition-fast), transform var(--transition-fast);
		text-decoration: none;
		color: inherit;
		cursor: pointer;
	}

	.spec-card:hover {
		border-color: var(--color-border-hover);
		box-shadow: var(--shadow-md);
		transform: translateY(-1px);
	}

	.spec-card.selected {
		border-color: var(--color-primary);
		background: var(--color-primary-light);
	}

	.spec-card-body {
		flex: 1;
		min-width: 0;
	}

	.spec-card-top {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-bottom: 4px;
	}

	.spec-subject {
		margin: 0;
		font-size: 1.05rem;
	}

	.spec-badges {
		display: flex;
		gap: 6px;
	}

	.badge {
		font-size: 0.7rem;
		padding: 2px 8px;
		border-radius: var(--radius-full);
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.3px;
	}

	.badge.reviewed {
		background: var(--color-success-bg);
		color: var(--color-success);
		border: 1px solid rgba(34, 197, 94, 0.3);
	}

	.spec-details {
		display: flex;
		gap: 12px;
		font-size: 0.85rem;
		color: var(--color-text-secondary);
		margin-bottom: 4px;
	}

	.spec-code {
		font-family: monospace;
		background: var(--color-surface-alt);
		padding: 1px 6px;
		border-radius: 3px;
	}

	.spec-description {
		font-size: 0.85rem;
		color: var(--color-text-secondary);
		margin: 4px 0 0;
		line-height: 1.3;
	}

	.spec-count {
		font-size: 0.8rem;
		color: var(--color-text-muted);
		margin-top: 2px;
	}

	.spec-card-actions {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-left: 16px;
	}

	.btn-toggle {
		padding: 8px 20px;
		font-size: 0.85rem;
		font-weight: 600;
		font-family: var(--font-body);
		border: 1.5px solid var(--color-border);
		border-radius: var(--radius-sm);
		background: var(--color-surface);
		color: var(--color-text);
		cursor: pointer;
		transition: all var(--transition-fast);
		width: auto;
		white-space: nowrap;
	}

	.btn-toggle:hover {
		background: var(--color-surface-alt);
	}

	.btn-toggle:active {
		transform: scale(0.97);
	}

	.btn-toggle.active {
		background: var(--color-primary);
		color: white;
		border-color: var(--color-primary);
	}

	.btn-toggle.active:hover {
		background: var(--color-primary-hover);
	}

	.btn-edit-spec,
	.btn-delete-spec {
		background: none;
		border: none;
		color: var(--color-text-muted);
		cursor: pointer;
		padding: 6px;
		border-radius: var(--radius-sm);
		display: flex;
		align-items: center;
		justify-content: center;
		transition: color var(--transition-fast), background var(--transition-fast);
		width: auto;
	}

	.btn-edit-spec:hover {
		color: var(--color-primary);
		background: var(--color-primary-light);
	}

	.btn-delete-spec:hover {
		color: var(--color-error);
		background: var(--color-error-bg);
	}

	@media (max-width: 600px) {
		.specs-header {
			flex-direction: column;
		}

		.filter-row {
			flex-direction: column;
		}

		.spec-card {
			flex-direction: column;
			align-items: stretch;
		}

		.spec-card-actions {
			margin-left: 0;
			margin-top: 12px;
			justify-content: flex-end;
		}
	}
</style>
