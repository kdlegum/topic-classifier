<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { fade } from 'svelte/transition';
	import { initAuth } from '$lib/auth';
	import Nav from '$lib/components/Nav.svelte';
	import '../app.css';

	let { children } = $props();

	onMount(() => {
		initAuth();
	});

	// Don't show nav on login page
	let showNav = $derived($page.url.pathname !== '/');
</script>

{#if showNav}
	<Nav />
{/if}

{#key $page.url.pathname}
	<div in:fade={{ duration: 200, delay: 100 }} out:fade={{ duration: 100 }}>
		{@render children()}
	</div>
{/key}
