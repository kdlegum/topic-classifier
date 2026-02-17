<script lang="ts">
	let {
		strands,
		selected = $bindable([]),
		label = 'Strands',
		hint = ''
	}: {
		strands: string[];
		selected: string[];
		label?: string;
		hint?: string;
	} = $props();

	function toggle(strand: string) {
		if (selected.includes(strand)) {
			selected = selected.filter((s) => s !== strand);
		} else {
			selected = [...selected, strand];
		}
	}
</script>

<div class="strand-picker">
	<span class="label">{label}</span>
	{#if hint}
		<p class="hint">{hint}</p>
	{/if}
	<div class="pills">
		{#each strands as strand}
			<button
				type="button"
				class="pill"
				class:active={selected.includes(strand)}
				onclick={() => toggle(strand)}
			>
				{strand}
			</button>
		{/each}
	</div>
</div>

<style>
	.strand-picker {
		margin-bottom: 16px;
	}

	.strand-picker .label {
		font-weight: 600;
		display: block;
		margin-bottom: 4px;
		font-size: 0.95rem;
		color: var(--color-text);
	}

	.hint {
		margin: 0 0 8px 0;
		font-size: 0.85rem;
		color: var(--color-text-secondary);
	}

	.pills {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}

	.pill {
		width: auto;
		padding: 6px 16px;
		border: 1.5px solid var(--color-border);
		border-radius: var(--radius-full);
		background: var(--color-surface);
		cursor: pointer;
		font-size: 0.9rem;
		font-weight: 600;
		font-family: var(--font-body);
		color: var(--color-text-secondary);
		transition: background var(--transition-fast), border-color var(--transition-fast), color var(--transition-fast), transform var(--transition-fast);
	}

	.pill:hover {
		border-color: var(--color-primary);
		color: var(--color-primary);
	}

	.pill:active {
		transform: scale(0.95);
	}

	.pill.active {
		background: var(--color-primary);
		color: #fff;
		border-color: var(--color-primary);
	}

	.pill.active:hover {
		background: var(--color-primary-hover);
		border-color: var(--color-primary-hover);
	}
</style>
