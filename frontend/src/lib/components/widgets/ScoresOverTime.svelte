<script lang="ts">
	import Chart from '$lib/components/Chart.svelte';
	import type { ChartConfiguration, ActiveElement, ChartEvent } from 'chart.js';
	import { goto } from '$app/navigation';

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

	let { sessions }: { sessions: SessionEntry[] } = $props();

	let markedSessions = $derived(sessions.filter((s) => s.percentage !== null));

	let chartConfig: ChartConfiguration = $derived.by(() => {
		const labels = markedSessions.map((s) => {
			if (!s.created_at) return 'Unknown';
			const d = new Date(s.created_at);
			return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
		});

		const data = markedSessions.map((s) => s.percentage!);

		const colors = data.map((pct) => {
			if (pct >= 70) return 'rgba(40, 167, 69, 0.7)';
			if (pct >= 50) return 'rgba(255, 193, 7, 0.7)';
			return 'rgba(220, 53, 69, 0.7)';
		});

		const borderColors = data.map((pct) => {
			if (pct >= 70) return '#28a745';
			if (pct >= 50) return '#ffc107';
			return '#dc3545';
		});

		return {
			type: 'bar' as const,
			data: {
				labels,
				datasets: [
					{
						label: 'Score %',
						data,
						backgroundColor: colors,
						borderColor: borderColors,
						borderWidth: 1
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				scales: {
					y: {
						beginAtZero: true,
						max: 100,
						title: { display: true, text: 'Score (%)' }
					},
					x: {
						title: { display: true, text: 'Session Date' }
					}
				},
				plugins: {
					tooltip: {
						callbacks: {
							afterLabel: (ctx: any) => {
								const s = markedSessions[ctx.dataIndex];
								return `${s.total_achieved}/${s.total_available} marks`;
							}
						}
					}
				}
			}
		};
	});

	function handleClick(elements: ActiveElement[], _event: ChartEvent) {
		if (elements.length > 0) {
			const idx = elements[0].index;
			const session = markedSessions[idx];
			if (session) {
				goto(`/mark_session/${session.session_id}`);
			}
		}
	}
</script>

{#if markedSessions.length === 0}
	<p class="empty-message">No marked sessions yet. Mark some sessions to see your scores over time.</p>
{:else}
	<div class="chart-container">
		<Chart config={chartConfig} onclick={handleClick} />
	</div>
{/if}

<style>
	.chart-container {
		position: relative;
		height: 300px;
	}
	.empty-message {
		text-align: center;
		color: #666;
		padding: 48px 24px;
	}
</style>
