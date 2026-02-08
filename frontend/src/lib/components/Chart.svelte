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

	onMount(() => {
		const opts = { ...config };
		if (onclick) {
			opts.options = {
				...opts.options,
				onClick: (event: ChartEvent, elements: ActiveElement[]) => {
					onclick!(elements, event);
				}
			};
		}
		chart = new ChartJS(canvas, opts);

		return () => {
			chart?.destroy();
			chart = null;
		};
	});

	$effect(() => {
		if (chart && config) {
			chart.data = config.data;
			const opts = config.options ?? {};
			if (onclick) {
				opts.onClick = (event: ChartEvent, elements: ActiveElement[]) => {
					onclick!(elements, event);
				};
			}
			chart.options = opts;
			chart.update();
		}
	});
</script>

<canvas bind:this={canvas}></canvas>
