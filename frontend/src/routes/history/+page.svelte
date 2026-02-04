<script lang="ts">
	import { onMount } from 'svelte';
	import { getUserSessions } from '$lib/api';

	let sessions: any[] | null = $state(null);
	let loading = $state(true);
	let error = $state(false);

	onMount(async () => {
		try {
			sessions = await getUserSessions();
		} catch (err) {
			console.error('Error loading sessions:', err);
			error = true;
		} finally {
			loading = false;
		}
	});

	function formatDate(dateStr: string): string {
		return new Date(dateStr).toLocaleDateString('en-GB', {
			day: 'numeric',
			month: 'short',
			year: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		});
	}

	function getTitle(session: any): string {
		const parts = [session.qualification, session.subject_name].filter(Boolean);
		return parts.length > 0 ? parts.join(' ') : session.subject;
	}
</script>

<svelte:head>
	<title>My Sessions - Topic Tracker</title>
</svelte:head>

<main class="page-content">
	<h1>My Sessions</h1>
	<p>View your past classification sessions.</p>

	<div class="sessions-list">
		{#if loading}
			<div class="loading">Loading sessions...</div>
		{:else if error}
			<div class="error-state">
				<p>Failed to load sessions. Please try again.</p>
			</div>
		{:else if sessions && sessions.length === 0}
			<div class="empty-state">
				<p>No sessions yet.</p>
				<p><a href="/classify">Classify some questions</a> to get started!</p>
			</div>
		{:else if sessions}
			{#each sessions as session}
				<a href="/mark_session/{session.session_id}" class="session-card">
					<div class="session-info">
						<div class="session-subject">{getTitle(session)}</div>
						<div class="session-meta">
							<span class="session-board">{session.exam_board}</span>
							<span class="session-date">{formatDate(session.created_at)}</span>
						</div>
					</div>
					<div class="session-questions">
						{session.question_count} question{session.question_count !== 1 ? 's' : ''}
					</div>
				</a>
			{/each}
		{/if}
	</div>
</main>
