<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
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

{@render children()}
