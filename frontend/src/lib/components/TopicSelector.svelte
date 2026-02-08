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

	let {
		specCode,
		corrections = $bindable([]),
		onchange
	}: {
		specCode: string;
		corrections: Correction[];
		onchange: (corrections: Correction[]) => void;
	} = $props();

	// Module-level cache for hierarchy data
	const hierarchyCache = new Map<string, Hierarchy>();

	let hierarchy: Hierarchy | null = $state(null);
	let loadingHierarchy = $state(false);

	let selectedStrand = $state('');
	let selectedTopic = $state('');
	let selectedSubtopic = $state('');

	let filteredTopics: Topic[] = $state([]);
	let filteredSubtopics: Subtopic[] = $state([]);

	async function loadHierarchy() {
		if (hierarchyCache.has(specCode)) {
			hierarchy = hierarchyCache.get(specCode)!;
			return;
		}
		loadingHierarchy = true;
		try {
			const data = await getTopicHierarchy(specCode);
			hierarchyCache.set(specCode, data);
			hierarchy = data;
		} catch (err) {
			console.error('Failed to load topic hierarchy:', err);
		} finally {
			loadingHierarchy = false;
		}
	}

	// Load hierarchy on mount
	$effect(() => {
		if (specCode) {
			loadHierarchy();
		}
	});

	function handleStrandChange(value: string) {
		selectedStrand = value;
		selectedTopic = '';
		selectedSubtopic = '';
		filteredSubtopics = [];

		if (hierarchy && value) {
			const strand = hierarchy.strands.find((s) => s.name === value);
			filteredTopics = strand ? strand.topics : [];
		} else {
			filteredTopics = [];
		}
	}

	function handleTopicChange(value: string) {
		selectedTopic = value;
		selectedSubtopic = '';

		if (value) {
			const topic = filteredTopics.find((t) => t.name === value);
			filteredSubtopics = topic ? topic.subtopics : [];
		} else {
			filteredSubtopics = [];
		}
	}

	function handleSubtopicChange(value: string) {
		selectedSubtopic = value;
	}

	function addCorrection() {
		if (!selectedSubtopic || !hierarchy) return;

		const subtopic = filteredSubtopics.find((s) => s.subtopic_id === selectedSubtopic);
		if (!subtopic) return;

		// Prevent duplicates
		if (corrections.some((c) => c.subtopic_id === subtopic.subtopic_id)) return;

		const newCorrection: Correction = {
			subtopic_id: subtopic.subtopic_id,
			strand: selectedStrand,
			topic: selectedTopic,
			subtopic: subtopic.name,
			spec_sub_section: subtopic.spec_sub_section,
			description: subtopic.description
		};

		corrections = [...corrections, newCorrection];
		onchange(corrections);

		// Reset dropdowns
		selectedSubtopic = '';
	}

	function removeCorrection(subtopicId: string) {
		corrections = corrections.filter((c) => c.subtopic_id !== subtopicId);
		onchange(corrections);
	}

	function isDuplicate(): boolean {
		return corrections.some((c) => c.subtopic_id === selectedSubtopic);
	}
</script>

<div class="topic-selector">
	<p class="topic-selector-label">Your topic selection</p>

	{#if corrections.length > 0}
		<div class="topic-chips">
			{#each corrections as correction}
				<span class="topic-chip" title={correction.description}>
					{correction.spec_sub_section}: {correction.subtopic}
					<button
						class="chip-remove"
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
		<div class="dropdown-row">
			<select
				value={selectedStrand}
				onchange={(e) => handleStrandChange(e.currentTarget.value)}
			>
				<option value="">Select strand...</option>
				{#each hierarchy.strands as strand}
					<option value={strand.name}>{strand.name}</option>
				{/each}
			</select>

			<select
				value={selectedTopic}
				onchange={(e) => handleTopicChange(e.currentTarget.value)}
				disabled={!selectedStrand}
			>
				<option value="">Select topic...</option>
				{#each filteredTopics as topic}
					<option value={topic.name}>{topic.name}</option>
				{/each}
			</select>

			<select
				value={selectedSubtopic}
				onchange={(e) => handleSubtopicChange(e.currentTarget.value)}
				disabled={!selectedTopic}
			>
				<option value="">Select subtopic...</option>
				{#each filteredSubtopics as subtopic}
					<option value={subtopic.subtopic_id}>{subtopic.spec_sub_section}: {subtopic.name}</option>
				{/each}
			</select>

			<button
				class="btn-add-topic"
				onclick={addCorrection}
				disabled={!selectedSubtopic || isDuplicate()}
			>Add</button>
		</div>
	{/if}
</div>
