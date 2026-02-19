<script module lang="ts">
	// Shared cache across all TopicSelector instances
	const hierarchyCache = new Map<string, any>();
	const inflightRequests = new Map<string, Promise<any>>();
</script>

<script lang="ts">
	import { getTopicHierarchy } from '$lib/api';

	type Subtopic = {
		subtopic_id: string;
		name: string;
		spec_sub_section: string;
		description: string;
	};

	type Topic = {
		topic_id: number;
		name: string;
		subtopics: Subtopic[];
	};

	type Strand = {
		name: string;
		topics: Topic[];
	};

	type Hierarchy = {
		spec_code: string;
		exam_board: string;
		strands: Strand[];
	};

	type Correction = {
		subtopic_id: string;
		strand: string;
		topic: string;
		subtopic: string;
		spec_sub_section: string;
		description: string;
	};

	type FlatSubtopic = {
		subtopic_id: string;
		name: string;
		spec_sub_section: string;
		description: string;
		strand: string;
		topic: string;
	};

	let {
		specCode,
		corrections = $bindable([]),
		onchange
	}: {
		specCode: string;
		corrections: Correction[];
		onchange: (corrections: Correction[]) => void;
	} = $props();

	let hierarchy: Hierarchy | null = $state(null);
	let loadingHierarchy = $state(false);

	let searchQuery = $state('');
	let showDropdown = $state(false);
	let activeIndex = $state(-1);
	let inputEl: HTMLInputElement | null = $state(null);
	let dropdownEl: HTMLElement | null = $state(null);

	async function loadHierarchy() {
		if (hierarchyCache.has(specCode)) {
			hierarchy = hierarchyCache.get(specCode)!;
			return;
		}
		loadingHierarchy = true;
		try {
			let promise = inflightRequests.get(specCode);
			if (!promise) {
				promise = getTopicHierarchy(specCode);
				inflightRequests.set(specCode, promise);
			}
			const data = await promise;
			hierarchyCache.set(specCode, data);
			inflightRequests.delete(specCode);
			hierarchy = data;
		} catch (err) {
			inflightRequests.delete(specCode);
			console.error('Failed to load topic hierarchy:', err);
		} finally {
			loadingHierarchy = false;
		}
	}

	$effect(() => {
		if (specCode) {
			loadHierarchy();
		}
	});

	// Flatten hierarchy to a searchable list
	let allSubtopics: FlatSubtopic[] = $derived(
		hierarchy
			? hierarchy.strands.flatMap((strand) =>
					strand.topics.flatMap((topic) =>
						topic.subtopics.map((sub) => ({
							subtopic_id: sub.subtopic_id,
							name: sub.name,
							spec_sub_section: sub.spec_sub_section,
							description: sub.description,
							strand: strand.name,
							topic: topic.name
						}))
					)
				)
			: []
	);

	let searchResults: FlatSubtopic[] = $derived.by(() => {
		const q = searchQuery.trim().toLowerCase();
		if (!q || q.length < 1) return [];
		return allSubtopics
			.filter(
				(s) =>
					s.name.toLowerCase().includes(q) ||
					s.spec_sub_section.toLowerCase().includes(q) ||
					s.topic.toLowerCase().includes(q) ||
					s.strand.toLowerCase().includes(q)
			)
			.slice(0, 10);
	});

	$effect(() => {
		// Reset active index when results change
		searchResults;
		activeIndex = -1;
	});

	function isAdded(subtopicId: string): boolean {
		return corrections.some((c) => c.subtopic_id === subtopicId);
	}

	function selectResult(result: FlatSubtopic) {
		if (isAdded(result.subtopic_id)) return;

		const newCorrection: Correction = {
			subtopic_id: result.subtopic_id,
			strand: result.strand,
			topic: result.topic,
			subtopic: result.name,
			spec_sub_section: result.spec_sub_section,
			description: result.description
		};

		corrections = [...corrections, newCorrection];
		onchange(corrections);
		searchQuery = '';
		showDropdown = false;
		activeIndex = -1;
	}

	function removeCorrection(subtopicId: string) {
		corrections = corrections.filter((c) => c.subtopic_id !== subtopicId);
		onchange(corrections);
	}

	function handleKeydown(e: KeyboardEvent) {
		if (!showDropdown || searchResults.length === 0) return;

		if (e.key === 'ArrowDown') {
			e.preventDefault();
			activeIndex = Math.min(activeIndex + 1, searchResults.length - 1);
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			activeIndex = Math.max(activeIndex - 1, -1);
		} else if (e.key === 'Enter' && activeIndex >= 0) {
			e.preventDefault();
			selectResult(searchResults[activeIndex]);
		} else if (e.key === 'Escape') {
			showDropdown = false;
			activeIndex = -1;
		}
	}

	function handleInputFocus() {
		if (searchQuery.trim()) {
			showDropdown = true;
		}
	}

	function handleClickOutside(e: MouseEvent) {
		const target = e.target as Node;
		if (inputEl && !inputEl.contains(target) && dropdownEl && !dropdownEl.contains(target)) {
			showDropdown = false;
		}
	}
</script>

<svelte:window onclick={handleClickOutside} />

<div class="topic-selector">
	<p class="topic-selector-label">Custom topic selection</p>

	{#if corrections.length > 0}
		<div class="topic-chips">
			{#each corrections as correction}
				<span class="topic-chip" title={correction.description}>
					{correction.spec_sub_section}: {correction.subtopic}
					<button
						class="chip-remove"
						tabindex="-1"
						onclick={() => removeCorrection(correction.subtopic_id)}
						aria-label="Remove {correction.subtopic}"
					>&times;</button>
				</span>
			{/each}
		</div>
	{/if}

	{#if loadingHierarchy}
		<p class="topic-selector-loading">Loading topics...</p>
	{:else if hierarchy}
		<div class="search-wrapper">
			<input
				bind:this={inputEl}
				class="topic-search"
				type="text"
				placeholder="Search topics..."
				tabindex="-1"
				autocomplete="off"
				bind:value={searchQuery}
				oninput={() => { showDropdown = searchQuery.trim().length > 0; }}
				onfocus={handleInputFocus}
				onkeydown={handleKeydown}
			/>
			{#if showDropdown && searchResults.length > 0}
				<div class="search-dropdown" bind:this={dropdownEl}>
					{#each searchResults as result, i}
						{@const added = isAdded(result.subtopic_id)}
						<button
							class="search-result {i === activeIndex ? 'active' : ''} {added ? 'added' : ''}"
							tabindex="-1"
							onmousedown={(e) => { e.preventDefault(); selectResult(result); }}
						>
							<span class="result-name">{result.spec_sub_section}: {result.name}</span>
							<span class="result-path">{result.strand} › {result.topic}</span>
							{#if added}
								<span class="result-added-mark">&#10003;</span>
							{/if}
						</button>
					{/each}
				</div>
			{:else if showDropdown && searchQuery.trim().length > 0}
				<div class="search-dropdown" bind:this={dropdownEl}>
					<p class="no-results">No topics found</p>
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.topic-selector {
		margin-top: 12px;
	}

	.topic-selector-label {
		font-size: 0.8rem;
		font-weight: 600;
		color: var(--color-text-secondary);
		margin: 0 0 8px 0;
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}

	.topic-chips {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		margin-bottom: 8px;
	}

	.topic-chip {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 4px 8px 4px 10px;
		border-radius: var(--radius-full);
		background: var(--color-primary-light);
		color: var(--color-primary);
		font-size: 0.8rem;
		font-weight: 600;
	}

	.chip-remove {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		background: none;
		border: none;
		color: inherit;
		cursor: pointer;
		font-size: 1rem;
		line-height: 1;
		padding: 0;
		opacity: 0.7;
		transition: opacity var(--transition-fast);
	}

	.chip-remove:hover {
		opacity: 1;
	}

	.topic-selector-loading {
		font-size: 0.85rem;
		color: var(--color-text-secondary);
		margin: 0;
	}

	.search-wrapper {
		position: relative;
	}

	.topic-search {
		width: 100%;
		box-sizing: border-box;
		padding: 7px 12px;
		border: 1.5px solid var(--color-border);
		border-radius: var(--radius-sm);
		background: var(--color-surface);
		color: var(--color-text);
		font-family: var(--font-body);
		font-size: 0.9rem;
		transition: border-color var(--transition-fast);
	}

	.topic-search:focus {
		outline: none;
		border-color: var(--color-primary);
	}

	.search-dropdown {
		position: absolute;
		top: calc(100% + 4px);
		left: 0;
		right: 0;
		background: var(--color-surface);
		border: 1.5px solid var(--color-border);
		border-radius: var(--radius-sm);
		box-shadow: var(--shadow-md);
		z-index: 50;
		overflow: hidden;
	}

	.search-result {
		display: grid;
		grid-template-columns: 1fr auto;
		grid-template-rows: auto auto;
		gap: 2px 8px;
		align-items: center;
		width: 100%;
		padding: 8px 12px;
		border: none;
		background: none;
		text-align: left;
		cursor: pointer;
		font-family: var(--font-body);
		color: var(--color-text);
		transition: background var(--transition-fast);
		border-bottom: 1px solid var(--color-border);
	}

	.search-result:last-child {
		border-bottom: none;
	}

	.search-result:hover:not(.added),
	.search-result.active:not(.added) {
		background: var(--color-primary-light);
	}

	.search-result.added {
		cursor: default;
		opacity: 0.55;
	}

	.result-name {
		grid-row: 1;
		grid-column: 1;
		font-size: 0.875rem;
		font-weight: 600;
	}

	.result-path {
		grid-row: 2;
		grid-column: 1;
		font-size: 0.75rem;
		color: var(--color-text-secondary);
	}

	.result-added-mark {
		grid-row: 1 / 3;
		grid-column: 2;
		color: var(--color-success, #16a34a);
		font-size: 0.9rem;
	}

	.no-results {
		padding: 10px 12px;
		font-size: 0.875rem;
		color: var(--color-text-secondary);
		margin: 0;
	}
</style>
