<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	onMount(() => {
		const sessionId = $page.params.session_id;
		goto(`/mark_session/${sessionId}`, { replaceState: true });
	});
</script>

<main class="page-content">
	<div class="loading">Redirecting...</div>
</main>
