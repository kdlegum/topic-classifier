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
		border: 1.5px solid var(--color-border);
		border-radius: var(--radius-sm);
		font-size: 0.95rem;
		font-family: var(--font-body);
		box-sizing: border-box;
		background: var(--color-surface);
		transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
	}

	.search-input:focus {
		outline: none;
		border-color: var(--color-primary);
		box-shadow: 0 0 0 3px var(--color-primary-glow);
	}

	.empty-message {
		text-align: center;
		color: var(--color-text-secondary);
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
		border-radius: var(--radius-md);
		overflow: hidden;
		border: 1.5px solid var(--color-border);
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
		background: var(--color-surface-alt);
		color: var(--color-text-secondary);
	}

	.status-insecure .column-header {
		background: var(--color-error-bg);
		color: var(--color-error);
	}

	.status-secure .column-header {
		background: var(--color-warning-bg);
		color: #D97706;
	}

	.status-mastered .column-header {
		background: var(--color-success-bg);
		color: var(--color-success);
	}

	.count-badge {
		background: rgba(0, 0, 0, 0.08);
		border-radius: var(--radius-full);
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
		border-radius: var(--radius-sm);
		margin-bottom: 4px;
		transition: background var(--transition-fast);
	}

	.subtopic-item:hover {
		background: var(--color-surface-alt);
	}

	.subtopic-name {
		font-size: 0.88rem;
		font-weight: 600;
		color: var(--color-text);
	}

	.subtopic-meta {
		font-size: 0.78rem;
		color: var(--color-text-muted);
		margin-top: 2px;
	}

	.full-marks {
		margin-left: 6px;
		color: var(--color-success);
		font-weight: 600;
	}

	.column-empty {
		text-align: center;
		color: var(--color-text-muted);
		padding: 20px;
		font-size: 0.85rem;
	}
</style>
