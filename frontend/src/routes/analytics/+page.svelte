<script lang="ts">
	import { onMount } from 'svelte';
	import { getAnalyticsSummary, getProgress } from '$lib/api';
	import ScoresOverTime from '$lib/components/widgets/ScoresOverTime.svelte';
	import StrandPerformance from '$lib/components/widgets/StrandPerformance.svelte';
	import ProgressTracker from '$lib/components/widgets/ProgressTracker.svelte';

	type SessionEntry = {
		session_id: string;
		spec_code: string;
		subject_name: string | null;
		exam_board: string;
		created_at: string | null;
		question_count: number;
		total_available: number;
		total_achieved: number | null;
		percentage: number | null;
	};

	type StrandEntry = {
		spec_code: string;
		strand: string;
		marks_available: number;
		marks_achieved: number;
		question_count: number;
	};

	type TopicEntry = {
		spec_code: string;
		topic: string;
		marks_available: number;
		marks_achieved: number;
		question_count: number;
	};

	let loading = $state(true);
	let error = $state('');
	let sessionsOverTime: SessionEntry[] = $state([]);
	let strandPerformance: StrandEntry[] = $state([]);
	let topicPerformance: TopicEntry[] = $state([]);
	let selectedSpec = $state('');

	let progressData: any[] = $state([]);
	let progressLoading = $state(false);
	let progressError = $state('');

	// Collect unique specs from the data
	let specs = $derived.by(() => {
		const specMap = new Map<string, { spec_code: string; label: string }>();
		for (const s of sessionsOverTime) {
			if (!specMap.has(s.spec_code)) {
				const label = s.subject_name
					? `${s.exam_board} - ${s.subject_name}`
					: `${s.exam_board} - ${s.spec_code}`;
				specMap.set(s.spec_code, { spec_code: s.spec_code, label });
			}
		}
		return Array.from(specMap.values());
	});

	// Filter data by selected spec
	let filteredSessions = $derived(
		selectedSpec
			? sessionsOverTime.filter((s) => s.spec_code === selectedSpec)
			: sessionsOverTime
	);

	let filteredStrands = $derived(
		selectedSpec
			? strandPerformance.filter((s) => s.spec_code === selectedSpec)
			: strandPerformance
	);

	let filteredTopics = $derived(
		selectedSpec
			? topicPerformance.filter((t) => t.spec_code === selectedSpec)
			: topicPerformance
	);

	// Dynamic heading: show "Topic Performance" when single strand
	let performanceHeading = $derived.by(() => {
		const uniqueStrands = new Set(filteredStrands.map((s) => s.strand));
		return uniqueStrands.size <= 1 && filteredTopics.length > 0
			? 'Topic Performance'
			: 'Strand Performance';
	});

	// Fetch progress data when selectedSpec changes
	$effect(() => {
		const spec = selectedSpec;
		if (!spec) {
			progressData = [];
			progressError = '';
			return;
		}

		progressLoading = true;
		progressError = '';

		getProgress(spec)
			.then((data) => {
				progressData = data.subtopics;
			})
			.catch((e: any) => {
				progressError = e.message || 'Failed to load progress';
				progressData = [];
			})
			.finally(() => {
				progressLoading = false;
			});
	});

	onMount(async () => {
		try {
			const data = await getAnalyticsSummary();
			sessionsOverTime = data.sessions_over_time;
			strandPerformance = data.strand_performance;
			topicPerformance = data.topic_performance ?? [];

			// Auto-select if only one spec
			if (specs.length === 1) {
				selectedSpec = specs[0].spec_code;
			}
		} catch (e: any) {
			error = e.message || 'Failed to load analytics';
		} finally {
			loading = false;
		}
	});
</script>

<svelte:head>
	<title>Analytics: Topics Tracker</title>
</svelte:head>

<main class="page-content analytics-page">
	<h1>Analytics</h1>

	{#if loading}
		<p class="loading">Loading analytics...</p>
	{:else if error}
		<div class="error-state">
			<p>Failed to load analytics: {error}</p>
		</div>
	{:else if sessionsOverTime.length === 0}
		<div class="empty-state">
			<p>No sessions found. <a href="/classify">Classify some questions</a> to see your analytics.</p>
		</div>
	{:else}
		{#if specs.length > 1}
			<div class="spec-filter">
				<label for="spec-select">Specification:</label>
				<select id="spec-select" bind:value={selectedSpec}>
					<option value="">All specifications</option>
					{#each specs as spec}
						<option value={spec.spec_code}>{spec.label}</option>
					{/each}
				</select>
			</div>
		{/if}

		<div class="analytics-grid">
			<div class="widget-card">
				<h2>Scores Over Time</h2>
				<ScoresOverTime sessions={filteredSessions} />
			</div>

			<div class="widget-card">
				<h2>{performanceHeading}</h2>
				<StrandPerformance strandData={filteredStrands} topicData={filteredTopics} />
			</div>

			{#if selectedSpec}
				<div class="widget-card widget-wide">
					<h2>Progress Tracker</h2>
					{#if progressLoading}
						<p class="loading">Loading progress...</p>
					{:else if progressError}
						<p class="error-message">{progressError}</p>
					{:else}
						<ProgressTracker subtopics={progressData} />
					{/if}
				</div>
			{/if}
		</div>
	{/if}
</main>

<style>
	.analytics-page {
		max-width: 1100px;
	}

	.spec-filter {
		display: flex;
		align-items: center;
		gap: 12px;
		margin-bottom: 24px;
	}

	.spec-filter label {
		font-weight: 600;
		white-space: nowrap;
	}

	.spec-filter select {
		padding: 8px 12px;
		border: 1px solid #ccc;
		border-radius: 4px;
		font-size: 0.95rem;
		min-width: 240px;
	}

	.analytics-grid {
		display: grid;
		grid-template-columns: 1fr;
		gap: 24px;
	}

	@media (min-width: 900px) {
		.analytics-grid {
			grid-template-columns: 1fr 1fr;
		}
	}

	.widget-card {
		border: 1px solid #ddd;
		border-radius: 8px;
		padding: 20px;
		background: #fff;
	}

	.widget-card h2 {
		margin: 0 0 16px 0;
		font-size: 1.1rem;
		color: #333;
	}

	.widget-wide {
		grid-column: 1 / -1;
	}

	.error-message {
		color: #b71c1c;
		text-align: center;
		padding: 24px;
	}
</style>
