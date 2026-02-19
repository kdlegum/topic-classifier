<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { fade } from 'svelte/transition';
	import { initAuth } from '$lib/auth';
	import Nav from '$lib/components/Nav.svelte';
	import '../app.css';

	let { children } = $props();

	let contentEl: HTMLElement | null = $state(null);
	let thumbHeight = $state(0);
	let thumbTop = $state(0);

	let isDragging = false;
	let dragStartY = 0;
	let dragStartScrollTop = 0;

	function updateThumb() {
		if (!contentEl) return;
		const { scrollTop, scrollHeight, clientHeight } = contentEl;
		if (scrollHeight <= clientHeight) {
			thumbHeight = 0;
			return;
		}
		const ratio = clientHeight / scrollHeight;
		thumbHeight = Math.max(48, ratio * clientHeight);
		const maxThumbTop = clientHeight - thumbHeight;
		const maxScrollTop = scrollHeight - clientHeight;
		thumbTop = maxScrollTop > 0 ? (scrollTop / maxScrollTop) * maxThumbTop : 0;
	}

	function handleScroll() {
		updateThumb();
	}

	function handleThumbPointerDown(e: PointerEvent) {
		if (!contentEl) return;
		isDragging = true;
		dragStartY = e.clientY;
		dragStartScrollTop = contentEl.scrollTop;
		(e.target as HTMLElement).setPointerCapture(e.pointerId);
		e.preventDefault();
	}

	function handleThumbPointerMove(e: PointerEvent) {
		if (!isDragging || !contentEl) return;
		const { scrollHeight, clientHeight } = contentEl;
		const maxThumbTop = clientHeight - thumbHeight;
		const maxScrollTop = scrollHeight - clientHeight;
		if (maxThumbTop <= 0) return;
		const delta = e.clientY - dragStartY;
		const scrollDelta = (delta / maxThumbTop) * maxScrollTop;
		contentEl.scrollTop = Math.max(0, Math.min(dragStartScrollTop + scrollDelta, maxScrollTop));
		updateThumb();
	}

	function handleThumbPointerUp() {
		isDragging = false;
	}

	function handleTrackClick(e: MouseEvent) {
		if (!contentEl || isDragging) return;
		if ((e.target as HTMLElement).classList.contains('scrollbar-thumb')) return;
		const track = e.currentTarget as HTMLElement;
		const rect = track.getBoundingClientRect();
		const ratio = (e.clientY - rect.top) / rect.height;
		const { scrollHeight, clientHeight } = contentEl;
		contentEl.scrollTo({ top: ratio * (scrollHeight - clientHeight), behavior: 'smooth' });
	}

	// Keep thumb in sync whenever content or container size changes
	$effect(() => {
		if (!contentEl) return;
		updateThumb();
		const ro = new ResizeObserver(updateThumb);
		ro.observe(contentEl);
		return () => ro.disconnect();
	});

	// Reset thumb on route change
	$effect(() => {
		$page.url.pathname;
		setTimeout(updateThumb, 50);
	});

	onMount(() => {
		initAuth();
	});

	let showNav = $derived($page.url.pathname !== '/');
</script>

<div class="app-shell">
	{#if showNav}
		<Nav />
	{/if}
	<div class="app-outer">
		<div
			class="app-content"
			bind:this={contentEl}
			onscroll={handleScroll}
		>
			{#key $page.url.pathname}
				<div in:fade={{ duration: 200, delay: 100 }} out:fade={{ duration: 100 }}>
					{@render children()}
				</div>
			{/key}
		</div>

		<!-- Custom scrollbar -->
		<div
			class="scrollbar-track"
			onclick={handleTrackClick}
			role="scrollbar"
			aria-controls="app-content"
			aria-valuenow={Math.round((thumbTop / (contentEl?.clientHeight ?? 1)) * 100)}
			aria-valuemin={0}
			aria-valuemax={100}
			tabindex="-1"
		>
			{#if thumbHeight > 0}
				<div
					class="scrollbar-thumb"
					style="height: {thumbHeight}px; transform: translateY({thumbTop}px)"
					onpointerdown={handleThumbPointerDown}
					onpointermove={handleThumbPointerMove}
					onpointerup={handleThumbPointerUp}
					role="presentation"
				></div>
			{/if}
		</div>
	</div>
</div>

<style>
	:global(html), :global(body) {
		height: 100%;
		overflow: hidden;
	}

	.app-shell {
		display: flex;
		flex-direction: column;
		height: 100vh;
	}

	.app-outer {
		flex: 1;
		display: flex;
		overflow: hidden;
		min-height: 0;
	}

	.app-content {
		flex: 1;
		overflow-y: auto;
		overflow-x: hidden;
		scroll-padding-top: 16px;
		/* Hide native scrollbar in all browsers */
		scrollbar-width: none;
		-ms-overflow-style: none;
	}

	:global(.app-content::-webkit-scrollbar) {
		display: none;
		width: 0;
	}

	/* ── Custom scrollbar ── */
	.scrollbar-track {
		width: 16px;
		flex-shrink: 0;
		position: relative;
		background: transparent;
		cursor: default;
		padding: 4px 0;
	}

	.scrollbar-thumb {
		position: absolute;
		left: 4px;
		width: 8px;
		border-radius: 9999px;
		background: rgba(249, 115, 22, 0.45);
		cursor: grab;
		transition: background 0.15s ease, width 0.15s ease, left 0.15s ease;
		will-change: transform;
	}

	.scrollbar-track:hover .scrollbar-thumb {
		width: 10px;
		left: 3px;
		background: var(--color-accent);
	}

	.scrollbar-thumb:active {
		cursor: grabbing;
		background: var(--color-accent-hover);
	}
</style>
