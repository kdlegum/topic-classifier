<script lang="ts">
	import { onMount } from 'svelte';
	import { apiFetch } from '$lib/api';

	let {
		sessionId,
		pdfLocation
	}: {
		sessionId: string;
		pdfLocation: { start_page: number; start_y: number; end_page: number; end_y: number };
	} = $props();

	let containerEl: HTMLDivElement | undefined = $state();
	let status: 'loading' | 'ready' | 'error' = $state('loading');
	let errorMsg = $state('');

	// Module-level cache: sessionId -> promise that resolves to PDF document proxy
	const pdfLoadPromises = new Map<string, Promise<any>>();

	// PDF.js scale: render at 1.5x for clarity
	const RENDER_SCALE = 1.5;

	async function getOrLoadPdf(sid: string): Promise<any> {
		if (pdfLoadPromises.has(sid)) {
			return pdfLoadPromises.get(sid)!;
		}

		const promise = (async () => {
			const pdfjsLib = await import('pdfjs-dist');

			if (!pdfjsLib.GlobalWorkerOptions.workerSrc) {
				const workerModule = await import('pdfjs-dist/build/pdf.worker.min.mjs?url');
				pdfjsLib.GlobalWorkerOptions.workerSrc = workerModule.default;
			}

			const response = await apiFetch(`/session/${sid}/pdf`);
			if (!response.ok) {
				throw new Error(`Failed to load PDF: ${response.status}`);
			}
			const blob = await response.blob();
			const blobUrl = URL.createObjectURL(blob);

			const loadingTask = pdfjsLib.getDocument({
				url: blobUrl,
				useWorkerFetch: false,
				wasmUrl: '/'
			});
			return await loadingTask.promise;
		})();

		pdfLoadPromises.set(sid, promise);
		return promise;
	}

	async function loadAndRender() {
		if (!containerEl) return;

		try {
			const pdfDoc = await getOrLoadPdf(sessionId);

			// Clear container
			containerEl.innerHTML = '';

			// Determine page segments to render
			const { start_page, start_y, end_page, end_y } = pdfLocation;

			for (let pageIdx = start_page; pageIdx <= end_page; pageIdx++) {
				const page = await pdfDoc.getPage(pageIdx + 1); // pdfjs is 1-indexed
				const viewport = page.getViewport({ scale: RENDER_SCALE });

				// Determine crop region for this page (in PDF points, then scaled)
				let cropTop: number;
				let cropBottom: number;

				if (pageIdx === start_page && pageIdx === end_page) {
					cropTop = start_y * RENDER_SCALE;
					cropBottom = end_y * RENDER_SCALE;
				} else if (pageIdx === start_page) {
					cropTop = start_y * RENDER_SCALE;
					cropBottom = viewport.height;
				} else if (pageIdx === end_page) {
					cropTop = 0;
					cropBottom = end_y * RENDER_SCALE;
				} else {
					cropTop = 0;
					cropBottom = viewport.height;
				}

				const cropHeight = cropBottom - cropTop;
				if (cropHeight <= 0) continue;

				// Create canvas and render full page
				const canvas = document.createElement('canvas');
				canvas.width = viewport.width;
				canvas.height = viewport.height;

				const ctx = canvas.getContext('2d')!;
				await page.render({ canvasContext: ctx, viewport }).promise;

				// Create a wrapper div that crops the canvas
				const wrapper = document.createElement('div');
				wrapper.style.overflow = 'hidden';
				wrapper.style.height = `${cropHeight}px`;
				wrapper.style.width = `${viewport.width}px`;
				wrapper.style.position = 'relative';

				// Position canvas inside wrapper to show only the cropped region
				canvas.style.position = 'absolute';
				canvas.style.top = `-${cropTop}px`;
				canvas.style.left = '0';
				canvas.style.maxWidth = 'none'; // prevent CSS from shrinking canvas

				wrapper.appendChild(canvas);

				// Scale wrapper down to fit container width
				const scaleWrapper = document.createElement('div');
				scaleWrapper.style.width = '100%';
				scaleWrapper.style.overflow = 'hidden';
				scaleWrapper.appendChild(wrapper);

				containerEl.appendChild(scaleWrapper);
			}

			// Apply responsive scaling: scale wrappers to fit container width
			requestAnimationFrame(() => {
				if (!containerEl) return;
				const containerWidth = containerEl.clientWidth;
				const wrappers = containerEl.querySelectorAll<HTMLElement>(':scope > div');
				for (const scaleWrapper of wrappers) {
					const inner = scaleWrapper.firstElementChild as HTMLElement;
					if (!inner) continue;
					const canvasWidth = parseFloat(inner.style.width);
					if (canvasWidth > containerWidth) {
						const scale = containerWidth / canvasWidth;
						inner.style.transform = `scale(${scale})`;
						inner.style.transformOrigin = 'top left';
						scaleWrapper.style.height = `${parseFloat(inner.style.height) * scale}px`;
					}
				}
			});

			status = 'ready';
		} catch (err: any) {
			console.error('PDF render error:', err);
			errorMsg = err.message || 'Failed to render PDF';
			status = 'error';
		}
	}

	onMount(() => {
		loadAndRender();
	});
</script>

<div class="pdf-question-view" bind:this={containerEl}>
	{#if status === 'loading'}
		<div class="pdf-loading">Loading PDF view...</div>
	{/if}
	{#if status === 'error'}
		<div class="pdf-error">{errorMsg}</div>
	{/if}
</div>

<style>
	.pdf-question-view {
		border: 1px solid #e0e0e0;
		border-radius: 8px;
		overflow: hidden;
		background: #fff;
		min-height: 60px;
	}

	.pdf-loading {
		padding: 16px;
		color: #666;
		text-align: center;
	}

	.pdf-error {
		padding: 16px;
		color: #cc0000;
		text-align: center;
		font-size: 0.9rem;
	}
</style>
