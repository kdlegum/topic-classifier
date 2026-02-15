<script lang="ts">
	import { onMount } from 'svelte';
	import ChartJS from 'chart.js/auto';
	import type {
		Chart,
		ChartConfiguration,
		ActiveElement,
		ChartEvent
	} from 'chart.js';

	let { config, onclick }: {
		config: ChartConfiguration;
		onclick?: (elements: ActiveElement[], event: ChartEvent) => void;
	} = $props();

	let canvas: HTMLCanvasElement;
	let chart: Chart | null = null;
	let mounted = false;

	function buildConfig(): ChartConfiguration {
		const opts = { ...config };
		if (onclick) {
			opts.options = {
				...opts.options,
				onClick: (event: ChartEvent, elements: ActiveElement[]) => {
					onclick!(elements, event);
				}
			};
		}
		return opts;
	}

	onMount(() => {
		mounted = true;
		chart = new ChartJS(canvas, buildConfig());
		return () => {
			chart?.destroy();
			chart = null;
			mounted = false;
		};
	});

	$effect(() => {
		// Re-read config to track it as a dependency
		const _ = config;
		if (!mounted || !chart) return;
		chart.destroy();
		chart = new ChartJS(canvas, buildConfig());
	});
</script>

<canvas bind:this={canvas}></canvas>
