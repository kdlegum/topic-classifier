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

			const { start_page, start_y, end_page, end_y } = pdfLocation;
			const containerWidth = containerEl.clientWidth || 600;

			for (let pageIdx = start_page; pageIdx <= end_page; pageIdx++) {
				const page = await pdfDoc.getPage(pageIdx + 1); // pdfjs is 1-indexed
				const baseViewport = page.getViewport({ scale: 1 });

				// Determine crop region in PDF user units (scale-independent)
				let cropTop: number;
				let cropBottom: number;

				if (pageIdx === start_page && pageIdx === end_page) {
					cropTop = start_y;
					cropBottom = end_y;
				} else if (pageIdx === start_page) {
					cropTop = start_y;
					cropBottom = baseViewport.height;
				} else if (pageIdx === end_page) {
					cropTop = 0;
					cropBottom = end_y;
				} else {
					cropTop = 0;
					cropBottom = baseViewport.height;
				}

				const cropHeightPt = cropBottom - cropTop;
				if (cropHeightPt <= 0) continue;

				// Scale to fit container width without exceeding RENDER_SCALE quality cap
				const fitScale = Math.min(RENDER_SCALE, containerWidth / baseViewport.width);
				const viewport = page.getViewport({ scale: fitScale });

				const cropTopPx = Math.round(cropTop * fitScale);
				const cropHeightPx = Math.round(cropHeightPt * fitScale);
				const pageWidthPx = Math.round(viewport.width);
				const pageHeightPx = Math.round(viewport.height);

				// Render full page to an offscreen canvas
				const offscreen = document.createElement('canvas');
				offscreen.width = pageWidthPx;
				offscreen.height = pageHeightPx;
				const offCtx = offscreen.getContext('2d')!;
				await page.render({ canvasContext: offCtx, viewport }).promise;

				// Copy only the cropped region to the display canvas
				const canvas = document.createElement('canvas');
				canvas.width = pageWidthPx;
				canvas.height = cropHeightPx;
				canvas.style.display = 'block';
				canvas.style.margin = '0 auto';
				canvas.style.maxWidth = '100%';

				const ctx = canvas.getContext('2d')!;
				ctx.drawImage(offscreen, 0, cropTopPx, pageWidthPx, cropHeightPx, 0, 0, pageWidthPx, cropHeightPx);

				containerEl.appendChild(canvas);
			}

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
