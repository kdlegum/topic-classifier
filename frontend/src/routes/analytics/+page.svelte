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

	type RawStrandEntry = {
		session_id: string;
		spec_code: string;
		strand: string;
		marks_available: number;
		marks_achieved: number;
		question_count: number;
	};

	type RawTopicEntry = {
		session_id: string;
		spec_code: string;
		strand: string;
		topic: string;
		marks_available: number;
		marks_achieved: number;
		question_count: number;
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
		strand: string;
		topic: string;
		marks_available: number;
		marks_achieved: number;
		question_count: number;
	};

	const timeframeOptions = [
		{ value: 'all', label: 'All Time' },
		{ value: '1w', label: 'Last Week' },
		{ value: '1m', label: 'Last Month' },
		{ value: '3m', label: '3 Months' },
		{ value: '6m', label: '6 Months' },
		{ value: '1y', label: '1 Year' }
	];

	let loading = $state(true);
	let error = $state('');
	let selectedSpec = $state('');
	let selectedTimeframe = $state('all');

	// Raw data from the single API fetch
	let allSessions: SessionEntry[] = $state([]);
	let allRawStrands: RawStrandEntry[] = $state([]);
	let allRawTopics: RawTopicEntry[] = $state([]);
	let strandsPerSpec: Record<string, number> = $state({});

	let progressData: any[] = $state([]);
	let progressLoading = $state(false);
	let progressError = $state('');

	function getFromDate(timeframe: string): Date | null {
		if (timeframe === 'all') return null;
		const now = new Date();
		switch (timeframe) {
			case '1w':
				now.setDate(now.getDate() - 7);
				break;
			case '1m':
				now.setMonth(now.getMonth() - 1);
				break;
			case '3m':
				now.setMonth(now.getMonth() - 3);
				break;
			case '6m':
				now.setMonth(now.getMonth() - 6);
				break;
			case '1y':
				now.setFullYear(now.getFullYear() - 1);
				break;
		}
		return now;
	}

	// Filter sessions by timeframe
	let sessionsOverTime = $derived.by(() => {
		const cutoff = getFromDate(selectedTimeframe);
		if (!cutoff) return allSessions;
		return allSessions.filter((s) => {
			if (!s.created_at) return false;
			return new Date(s.created_at) >= cutoff;
		});
	});

	// Set of session IDs within the timeframe
	let validSessionIds = $derived(new Set(sessionsOverTime.map((s) => s.session_id)));

	// Aggregate raw per-session strand data into grouped strand entries
	let strandPerformance: StrandEntry[] = $derived.by(() => {
		const agg = new Map<string, StrandEntry>();
		for (const r of allRawStrands) {
			if (!validSessionIds.has(r.session_id)) continue;
			const key = `${r.spec_code}::${r.strand}`;
			const existing = agg.get(key);
			if (existing) {
				existing.marks_available += r.marks_available;
				existing.marks_achieved += r.marks_achieved;
				existing.question_count += r.question_count;
			} else {
				agg.set(key, {
					spec_code: r.spec_code,
					strand: r.strand,
					marks_available: r.marks_available,
					marks_achieved: r.marks_achieved,
					question_count: r.question_count
				});
			}
		}
		return Array.from(agg.values()).map((v) => ({
			...v,
			marks_available: Math.round(v.marks_available * 10) / 10,
			marks_achieved: Math.round(v.marks_achieved * 10) / 10
		}));
	});

	// Aggregate raw per-session topic data into grouped topic entries
	let topicPerformance: TopicEntry[] = $derived.by(() => {
		const agg = new Map<string, TopicEntry>();
		for (const r of allRawTopics) {
			if (!validSessionIds.has(r.session_id)) continue;
			const key = `${r.spec_code}::${r.topic}`;
			const existing = agg.get(key);
			if (existing) {
				existing.marks_available += r.marks_available;
				existing.marks_achieved += r.marks_achieved;
				existing.question_count += r.question_count;
			} else {
				agg.set(key, {
					spec_code: r.spec_code,
					strand: r.strand,
					topic: r.topic,
					marks_available: r.marks_available,
					marks_achieved: r.marks_achieved,
					question_count: r.question_count
				});
			}
		}
		return Array.from(agg.values()).map((v) => ({
			...v,
			marks_available: Math.round(v.marks_available * 10) / 10,
			marks_achieved: Math.round(v.marks_achieved * 10) / 10
		}));
	});

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

	// Subject-level aggregation for "All Specifications" view
	let subjectPerformance = $derived.by(() => {
		if (selectedSpec) return [];
		const agg = new Map<string, { subject: string; marks_available: number; marks_achieved: number; question_count: number }>();
		for (const s of strandPerformance) {
			if (!agg.has(s.spec_code)) {
				const session = sessionsOverTime.find((se) => se.spec_code === s.spec_code);
				agg.set(s.spec_code, {
					subject: session?.subject_name ?? s.spec_code,
					marks_available: 0,
					marks_achieved: 0,
					question_count: 0
				});
			}
			const entry = agg.get(s.spec_code)!;
			entry.marks_available += s.marks_available;
			entry.marks_achieved += s.marks_achieved;
			entry.question_count += s.question_count;
		}
		return Array.from(agg.values());
	});

	// Whether the selected spec has multiple strands (from spec definition, not user data)
	let hasMultipleStrands = $derived.by(() => {
		if (!selectedSpec) return false;
		return (strandsPerSpec[selectedSpec] ?? 1) > 1;
	});

	// Dynamic heading
	let performanceHeading = $derived.by(() => {
		if (!selectedSpec) return 'Subject Performance';
		return hasMultipleStrands ? 'Strand Performance' : 'Topic Performance';
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
			allSessions = data.sessions_over_time;
			allRawStrands = data.strand_performance;
			allRawTopics = data.topic_performance ?? [];
			strandsPerSpec = data.strands_per_spec ?? {};

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
	{:else if allSessions.length === 0}
		<div class="empty-state">
			<p>No sessions found. <a href="/classify">Classify some questions</a> to see your analytics.</p>
		</div>
	{:else}
		<div class="filters-row">
			{#if specs.length > 1}
				<div class="filter-group">
					<label for="spec-select">Specification:</label>
					<select id="spec-select" bind:value={selectedSpec}>
						<option value="">All specifications</option>
						{#each specs as spec}
							<option value={spec.spec_code}>{spec.label}</option>
						{/each}
					</select>
				</div>
			{/if}

			<div class="filter-group">
				<label for="timeframe-select">Timeframe:</label>
				<select id="timeframe-select" bind:value={selectedTimeframe}>
					{#each timeframeOptions as opt}
						<option value={opt.value}>{opt.label}</option>
					{/each}
				</select>
			</div>
		</div>

		{#if sessionsOverTime.length === 0}
			<div class="empty-state">
				<p>No sessions found in this timeframe.</p>
			</div>
		{:else}
			<div class="analytics-grid">
				<div class="widget-card">
					<h2>Scores Over Time</h2>
					<ScoresOverTime sessions={filteredSessions} />
				</div>

				<div class="widget-card">
					<h2>{performanceHeading}</h2>
					<StrandPerformance
					strandData={selectedSpec ? filteredStrands : []}
					topicData={selectedSpec ? filteredTopics : []}
					subjectData={subjectPerformance}
					{hasMultipleStrands}
				/>
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
	{/if}
</main>

<style>
	.analytics-page {
		max-width: 1100px;
	}

	.filters-row {
		display: flex;
		align-items: center;
		gap: 24px;
		margin-bottom: 24px;
		flex-wrap: wrap;
	}

	.filter-group {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.filter-group label {
		font-weight: 600;
		white-space: nowrap;
		margin: 0;
	}

	.filter-group select {
		padding: 8px 12px;
		border: 1px solid #ccc;
		border-radius: 4px;
		font-size: 0.95rem;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
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
