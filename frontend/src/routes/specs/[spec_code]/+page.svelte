<script lang="ts">
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import { getSpec, addUserSpec, removeUserSpec, getSpecs, type SpecDetail, type SpecInfo, type TopicInput } from '$lib/api';

	const specCode = $page.params.spec_code!;

	let spec: SpecDetail | null = $state(null);
	let loading = $state(true);
	let errorMsg = $state('');
	let isSelected = $state(false);
	let toggling = $state(false);

	onMount(async () => {
		try {
			const [detail, allSpecs] = await Promise.all([
				getSpec(specCode),
				getSpecs()
			]);
			spec = detail;
			const match = allSpecs.find((s: SpecInfo) => s.spec_code === specCode);
			if (match) isSelected = !!match.is_selected;
		} catch (err: any) {
			errorMsg = err.message || 'Failed to load specification.';
		} finally {
			loading = false;
		}
	});

	async function toggleSpec() {
		toggling = true;
		try {
			if (isSelected) {
				await removeUserSpec(specCode);
				isSelected = false;
			} else {
				await addUserSpec(specCode);
				isSelected = true;
			}
		} catch (err: any) {
			console.error('Failed to toggle spec:', err);
		} finally {
			toggling = false;
		}
	}

	// Group topics by strand
	let topicsByStrand = $derived.by(() => {
		if (!spec) return new Map<string, TopicInput[]>();
		const map = new Map<string, TopicInput[]>();
		for (const t of spec.topics) {
			const existing = map.get(t.strand) ?? [];
			existing.push(t);
			map.set(t.strand, existing);
		}
		return map;
	});

	let totalSubtopics = $derived.by(() => {
		if (!spec) return 0;
		return spec.topics.reduce((sum: number, t: TopicInput) => sum + t.subtopics.length, 0);
	});
</script>

<svelte:head>
	<title>{spec ? `${spec.subject} - ${spec.spec_code}` : 'Specification'} - Topic Tracker</title>
</svelte:head>

<main class="page-content view-spec-page">
	<a href="/specs" class="back-link">&larr; Back to Specifications</a>

	{#if loading}
		<div class="loading">Loading specification...</div>
	{:else if errorMsg}
		<div class="error-banner">{errorMsg}</div>
	{:else if spec}
		<div class="spec-header">
			<div class="spec-header-info">
				<h1>{spec.subject}</h1>
				<div class="spec-meta">
					<span class="meta-item">{spec.exam_board}</span>
					<span class="meta-item">{spec.qualification}</span>
					<span class="meta-code">{spec.spec_code}</span>
					{#if spec.is_reviewed}
						<span class="badge reviewed">Reviewed</span>
					{/if}
				</div>
				{#if spec.description}
					<p class="spec-desc">{spec.description}</p>
				{/if}
				<div class="spec-stats">
					{spec.topics.length} topic{spec.topics.length !== 1 ? 's' : ''} &middot; {totalSubtopics} subtopic{totalSubtopics !== 1 ? 's' : ''} &middot; {topicsByStrand.size} strand{topicsByStrand.size !== 1 ? 's' : ''}
				</div>
			</div>
			<div class="spec-header-actions">
				<button
					class="btn-toggle"
					class:active={isSelected}
					onclick={toggleSpec}
					disabled={toggling}
				>
					{isSelected ? 'Remove from My Specs' : 'Add to My Specs'}
				</button>
			</div>
		</div>

		{#each [...topicsByStrand] as [strand, topics]}
			<div class="strand-section">
				<h2 class="strand-title">{strand}</h2>
				{#each topics as topic, tIdx}
					<div class="topic-block">
						<h3 class="topic-name">{topic.topic_name}</h3>
						<table class="subtopic-table">
							<thead>
								<tr>
									<th class="col-name">Subtopic</th>
									<th class="col-desc">Description</th>
								</tr>
							</thead>
							<tbody>
								{#each topic.subtopics as sub}
									<tr>
										<td class="sub-name">{sub.subtopic_name}</td>
										<td class="sub-desc">{sub.description}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{/each}
			</div>
		{/each}
	{/if}
</main>

<style>
	.view-spec-page {
		max-width: 900px;
	}

	.loading {
		text-align: center;
		color: #666;
		padding: 40px 0;
	}

	.error-banner {
		background: #fdecea;
		color: #8b0000;
		padding: 10px 16px;
		border-radius: 6px;
		margin-bottom: 20px;
		font-size: 0.9rem;
		border: 1px solid #f5c6cb;
	}

	.spec-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 16px;
		margin-bottom: 32px;
	}

	.spec-header-info {
		flex: 1;
		min-width: 0;
	}

	.spec-header h1 {
		margin: 0 0 8px;
		font-size: 1.5rem;
	}

	.spec-meta {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 10px;
		font-size: 0.9rem;
		color: #666;
		margin-bottom: 6px;
	}

	.meta-code {
		font-family: monospace;
		background: #f0f0f0;
		padding: 2px 8px;
		border-radius: 4px;
		font-size: 0.85rem;
	}

	.badge.reviewed {
		font-size: 0.7rem;
		padding: 2px 8px;
		border-radius: 10px;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.3px;
		background: #e8f5e9;
		color: #2e7d32;
		border: 1px solid #a5d6a7;
	}

	.spec-desc {
		color: #555;
		font-size: 0.9rem;
		margin: 4px 0 0;
		line-height: 1.4;
	}

	.spec-stats {
		font-size: 0.85rem;
		color: #888;
		margin-top: 6px;
	}

	.spec-header-actions {
		flex-shrink: 0;
	}

	.btn-toggle {
		padding: 10px 20px;
		font-size: 0.9rem;
		border: 1px solid #ddd;
		border-radius: 6px;
		background: #f5f5f5;
		color: #333;
		cursor: pointer;
		transition: all 0.2s;
		white-space: nowrap;
	}

	.btn-toggle:hover {
		background: #e8e8e8;
	}

	.btn-toggle.active {
		background: #0077cc;
		color: white;
		border-color: #0077cc;
	}

	.btn-toggle.active:hover {
		background: #005fa3;
	}

	.btn-toggle:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.strand-section {
		margin-bottom: 28px;
	}

	.strand-title {
		font-size: 1.1rem;
		color: #333;
		margin: 0 0 12px;
		padding-bottom: 6px;
		border-bottom: 2px solid #0077cc;
	}

	.topic-block {
		margin-bottom: 16px;
	}

	.topic-name {
		font-size: 0.95rem;
		font-weight: 600;
		color: #444;
		margin: 0 0 8px;
	}

	.subtopic-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.9rem;
	}

	.subtopic-table th {
		text-align: left;
		padding: 6px 12px;
		background: #f5f5f5;
		border: 1px solid #e0e0e0;
		font-weight: 600;
		font-size: 0.8rem;
		color: #666;
		text-transform: uppercase;
		letter-spacing: 0.3px;
	}

	.subtopic-table td {
		padding: 8px 12px;
		border: 1px solid #e8e8e8;
		vertical-align: top;
	}

	.col-name {
		width: 30%;
	}

	.sub-name {
		font-weight: 500;
		color: #333;
	}

	.sub-desc {
		color: #555;
		line-height: 1.4;
	}

	.subtopic-table tbody tr:hover {
		background: #fafafa;
	}

	@media (max-width: 600px) {
		.spec-header {
			flex-direction: column;
		}

		.subtopic-table th,
		.subtopic-table td {
			padding: 6px 8px;
			font-size: 0.85rem;
		}

		.col-name {
			width: 40%;
		}
	}
</style>
