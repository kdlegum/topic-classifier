<script lang="ts">
	import Chart from '$lib/components/Chart.svelte';
	import type { ChartConfiguration } from 'chart.js';

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

	type SubjectEntry = {
		subject: string;
		marks_available: number;
		marks_achieved: number;
		question_count: number;
	};

	let {
		strandData = [],
		topicData = [],
		subjectData = [],
		hasMultipleStrands = false
	}: {
		strandData?: StrandEntry[];
		topicData?: TopicEntry[];
		subjectData?: SubjectEntry[];
		hasMultipleStrands?: boolean;
	} = $props();

	let viewMode = $derived.by(() => {
		if (subjectData.length > 0) return 'subject';
		if (hasMultipleStrands) return 'strand';
		return 'topic';
	});

	const STRAND_PALETTE = [
		'#0077cc', '#2ecc71', '#e67e22', '#9b59b6', '#e74c3c', '#1abc9c', '#f39c12', '#3498db'
	];

	let strandColorMap = $derived.by(() => {
		const strands = [...new Set(strandData.map((s) => s.strand))];
		const map: Record<string, string> = {};
		strands.forEach((s, i) => {
			map[s] = STRAND_PALETTE[i % STRAND_PALETTE.length];
		});
		return map;
	});

	// ── Subject bar chart (All Specifications) ──
	let subjectChartConfig: ChartConfiguration = $derived.by(() => {
		const labels = subjectData.map((s) => s.subject);
		const data = subjectData.map((s) =>
			s.marks_available > 0 ? Math.round((s.marks_achieved / s.marks_available) * 100) : 0
		);
		return {
			type: 'bar' as const,
			data: {
				labels,
				datasets: [
					{
						label: 'Score %',
						data,
						backgroundColor: STRAND_PALETTE.slice(0, subjectData.length),
						borderRadius: 4
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				indexAxis: 'y' as const,
				scales: {
					x: { beginAtZero: true, max: 100, title: { display: true, text: 'Score %' } },
					y: { ticks: { autoSkip: false } }
				},
				plugins: {
					legend: { display: false },
					tooltip: {
						callbacks: {
							afterLabel: (ctx: any) => {
								const s = subjectData[ctx.dataIndex];
								return `${s.marks_achieved}/${s.marks_available} marks (${s.question_count} questions)`;
							}
						}
					}
				}
			}
		};
	});

	// ── Strand radar chart ──
	let strandChartConfig: ChartConfiguration = $derived.by(() => {
		const labels = strandData.map((s) => s.strand);
		const data = strandData.map((s) =>
			s.marks_available > 0 ? Math.round((s.marks_achieved / s.marks_available) * 100) : 0
		);
		const colors = strandData.map((s) => strandColorMap[s.strand] || '#0077cc');
		return {
			type: 'radar' as const,
			data: {
				labels,
				datasets: [
					{
						label: 'Score %',
						data,
						backgroundColor: 'rgba(0, 119, 204, 0.15)',
						borderColor: '#0077cc',
						borderWidth: 2,
						pointBackgroundColor: colors,
						pointRadius: 5
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				scales: {
					r: { beginAtZero: true, max: 100, ticks: { stepSize: 20 } }
				},
				plugins: {
					tooltip: {
						callbacks: {
							afterLabel: (ctx: any) => {
								const s = strandData[ctx.dataIndex];
								return `${s.marks_achieved}/${s.marks_available} marks (${s.question_count} questions)`;
							}
						}
					}
				}
			}
		};
	});

	// ── Topic horizontal bar chart (colored by strand, for multi-strand specs) ──
	let sortedTopics = $derived([...topicData].sort((a, b) => a.strand.localeCompare(b.strand)));
	let topicBarHeight = $derived(Math.max(200, sortedTopics.length * 30));

	let topicBarConfig: ChartConfiguration = $derived.by(() => {
		const strands = [...new Set(sortedTopics.map((t) => t.strand))];
		const labels = sortedTopics.map((t) => t.topic);

		const datasets = strands.map((strand) => {
			const color = strandColorMap[strand] || '#999';
			return {
				label: strand,
				data: sortedTopics.map((t) =>
					t.strand === strand
						? t.marks_available > 0
							? Math.round((t.marks_achieved / t.marks_available) * 100)
							: 0
						: null
				),
				backgroundColor: color + 'cc',
				borderColor: color,
				borderWidth: 1,
				borderRadius: 3
			};
		});

		return {
			type: 'bar' as const,
			data: { labels, datasets },
			options: {
				responsive: true,
				maintainAspectRatio: false,
				indexAxis: 'y' as const,
				scales: {
					x: { beginAtZero: true, max: 100, title: { display: true, text: 'Score %' } },
					y: { ticks: { autoSkip: false, font: { size: 11 } } }
				},
				plugins: {
					legend: { display: true, position: 'top' as const },
					tooltip: {
						callbacks: {
							afterLabel: (ctx: any) => {
								const t = sortedTopics[ctx.dataIndex];
								return `${t.marks_achieved}/${t.marks_available} marks (${t.question_count} questions)`;
							}
						}
					}
				}
			}
		};
	});

	// ── Topic radar chart (for single-strand specs) ──
	let topicRadarConfig: ChartConfiguration = $derived.by(() => {
		const labels = topicData.map((t) => t.topic);
		const data = topicData.map((t) =>
			t.marks_available > 0 ? Math.round((t.marks_achieved / t.marks_available) * 100) : 0
		);
		return {
			type: 'radar' as const,
			data: {
				labels,
				datasets: [
					{
						label: 'Score %',
						data,
						backgroundColor: 'rgba(0, 119, 204, 0.2)',
						borderColor: '#0077cc',
						borderWidth: 2,
						pointBackgroundColor: '#0077cc'
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				scales: {
					r: { beginAtZero: true, max: 100, ticks: { stepSize: 20 } }
				},
				plugins: {
					tooltip: {
						callbacks: {
							afterLabel: (ctx: any) => {
								const t = topicData[ctx.dataIndex];
								return `${t.marks_achieved}/${t.marks_available} marks (${t.question_count} questions)`;
							}
						}
					}
				}
			}
		};
	});

	let isEmpty = $derived(
		viewMode === 'subject'
			? subjectData.length === 0
			: viewMode === 'strand'
				? strandData.length === 0
				: topicData.length === 0
	);
</script>

{#if isEmpty}
	<p class="empty-message">No performance data yet. Mark some sessions to see your performance.</p>
{:else if viewMode === 'subject'}
	<div class="chart-container" style="height: {Math.max(200, subjectData.length * 50)}px">
		<Chart config={subjectChartConfig} />
	</div>
{:else if viewMode === 'strand'}
	<div class="chart-container">
		<Chart config={strandChartConfig} />
	</div>
	{#if topicData.length > 0}
		<h3 class="subsection-heading">Topic Breakdown</h3>
		<div class="chart-container" style="height: {topicBarHeight}px">
			<Chart config={topicBarConfig} />
		</div>
	{/if}
{:else}
	<div class="chart-container">
		<Chart config={topicRadarConfig} />
	</div>
{/if}

<style>
	.chart-container {
		position: relative;
		height: 350px;
	}
	.subsection-heading {
		margin: 20px 0 8px 0;
		font-size: 0.95rem;
		color: #555;
	}
	.empty-message {
		text-align: center;
		color: #666;
		padding: 48px 24px;
	}
</style>
