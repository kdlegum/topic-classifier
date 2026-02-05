<script lang="ts">
    import { onMount } from "svelte";
    import Chart from "$lib/components/Chart.svelte";
	import type { ChartConfiguration } from "chart.js";

    type AnalyticsChart = {
        title: string;
        config: ChartConfiguration;
    };

    let chart1: ChartConfiguration = {
        type: 'bar',
        data: {
            labels: ['Q1', 'Q2', 'Q3'],
            datasets: [{
                label: 'Marks',
                data: [4, 6, 7]
            }]
        }
    };

    let charts: AnalyticsChart[] = [
        {
            title: "Example 1",
            config: {
                type: 'radar',
                data: {
                    labels: ['Algebra', 'Calculus', 'Mechanics'],
                    datasets: [
                        {
                            label: 'Average',
                            data: [80, 65, 70]
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false
                }
            }
        },
        {
            title: "Example 2",
            config: chart1
        }
    ]

</script>

<svelte:head>
    <title>Analytics: Topics Tracker</title>
</svelte:head>

<main class="page-content">
    <h1>Analytics</h1>

    <div class="analytics-dashboard">
        {#each charts as chart (chart.title)}
            <div class="chart-title-container">
                <h2>{chart.title}</h2>
                <div class="chart-wrapper">
                    <Chart config={chart.config}/>
                </div>
            </div>
        {/each}
    </div>
</main>