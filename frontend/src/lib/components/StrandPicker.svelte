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
	<label>{label}</label>
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

	.strand-picker label {
		font-weight: 600;
		display: block;
		margin-bottom: 4px;
		font-size: 0.95rem;
	}

	.hint {
		margin: 0 0 8px 0;
		font-size: 0.85rem;
		color: #666;
	}

	.pills {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}

	.pill {
		width: auto;
		padding: 6px 16px;
		border: 1px solid #ccc;
		border-radius: 20px;
		background: #fff;
		cursor: pointer;
		font-size: 0.9rem;
		transition:
			background 0.15s,
			border-color 0.15s,
			color 0.15s;
	}

	.pill:hover {
		border-color: #0077cc;
	}

	.pill.active {
		background: #0077cc;
		color: #fff;
		border-color: #0077cc;
	}
</style>
