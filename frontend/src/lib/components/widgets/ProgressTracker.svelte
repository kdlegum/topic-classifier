<script lang="ts">
	type Subtopic = {
		subtopic_id: string;
		spec_sub_section: string;
		subtopic_name: string;
		strand: string;
		topic: string;
		status: string;
		full_marks_count: number;
		question_count: number;
	};

	let { subtopics }: { subtopics: Subtopic[] } = $props();

	let searchQuery = $state('');

	const statusOrder = ['not_revised', 'insecure', 'secure', 'mastered'] as const;

	const statusLabels: Record<string, string> = {
		not_revised: 'Not Revised',
		insecure: 'Insecure',
		secure: 'Secure',
		mastered: 'Mastered'
	};

	let filtered = $derived.by(() => {
		const q = searchQuery.toLowerCase().trim();
		if (!q) return subtopics;
		return subtopics.filter(
			(s) =>
				s.subtopic_name.toLowerCase().includes(q) ||
				s.strand.toLowerCase().includes(q) ||
				s.topic.toLowerCase().includes(q)
		);
	});

	let grouped = $derived.by(() => {
		const groups: Record<string, Subtopic[]> = {
			not_revised: [],
			insecure: [],
			secure: [],
			mastered: []
		};
		for (const s of filtered) {
			if (groups[s.status]) {
				groups[s.status].push(s);
			}
		}
		return groups;
	});
</script>

<div class="progress-tracker">
	<input
		type="text"
		class="search-input"
		placeholder="Search subtopics, strands, or topics..."
		bind:value={searchQuery}
	/>

	{#if subtopics.length === 0}
		<p class="empty-message">No progress data available for this specification.</p>
	{:else}
		<div class="status-columns">
			{#each statusOrder as status}
				<div class="status-column status-{status}">
					<div class="column-header">
						<span class="status-label">{statusLabels[status]}</span>
						<span class="count-badge">{grouped[status].length}</span>
					</div>
					<div class="column-list">
						{#each grouped[status] as item}
							<div class="subtopic-item">
								<div class="subtopic-name">{item.subtopic_name}</div>
								<div class="subtopic-meta">
									{item.strand} &rsaquo; {item.topic}
									{#if item.full_marks_count > 0}
										<span class="full-marks">{item.full_marks_count} full marks</span>
									{/if}
								</div>
							</div>
						{/each}
						{#if grouped[status].length === 0}
							<div class="column-empty">None</div>
						{/if}
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>

<style>
	.progress-tracker {
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	.search-input {
		width: 100%;
		padding: 10px 14px;
		border: 1px solid #ccc;
		border-radius: 6px;
		font-size: 0.95rem;
		box-sizing: border-box;
	}

	.search-input:focus {
		outline: none;
		border-color: #0077cc;
		box-shadow: 0 0 0 2px rgba(0, 119, 204, 0.15);
	}

	.empty-message {
		text-align: center;
		color: #666;
		padding: 48px 24px;
	}

	.status-columns {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 12px;
	}

	@media (max-width: 900px) {
		.status-columns {
			grid-template-columns: 1fr;
		}
	}

	.status-column {
		border-radius: 8px;
		overflow: hidden;
		border: 1px solid #e0e0e0;
	}

	.column-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 10px 14px;
		font-weight: 600;
		font-size: 0.9rem;
	}

	.status-not_revised .column-header {
		background: #f0f0f0;
		color: #555;
	}

	.status-insecure .column-header {
		background: #fdecea;
		color: #b71c1c;
	}

	.status-secure .column-header {
		background: #fff8e1;
		color: #e65100;
	}

	.status-mastered .column-header {
		background: #e8f5e9;
		color: #2e7d32;
	}

	.count-badge {
		background: rgba(0, 0, 0, 0.1);
		border-radius: 12px;
		padding: 2px 8px;
		font-size: 0.8rem;
		min-width: 20px;
		text-align: center;
	}

	.column-list {
		max-height: 400px;
		overflow-y: auto;
		padding: 8px;
	}

	.subtopic-item {
		padding: 8px 10px;
		border-radius: 4px;
		margin-bottom: 4px;
	}

	.subtopic-item:hover {
		background: #f5f5f5;
	}

	.subtopic-name {
		font-size: 0.88rem;
		font-weight: 500;
		color: #333;
	}

	.subtopic-meta {
		font-size: 0.78rem;
		color: #888;
		margin-top: 2px;
	}

	.full-marks {
		margin-left: 6px;
		color: #2e7d32;
		font-weight: 500;
	}

	.column-empty {
		text-align: center;
		color: #aaa;
		padding: 20px;
		font-size: 0.85rem;
	}
</style>
