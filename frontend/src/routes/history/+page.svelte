<script lang="ts">
	import { onMount } from 'svelte';
	import { getUserSessions, deleteSession } from '$lib/api';

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

	async function handleDelete(e: Event, sessionId: string) {
		e.preventDefault();
		e.stopPropagation();
		if (!confirm('Are you sure you want to delete this session? This cannot be undone.')) return;
		try {
			await deleteSession(sessionId);
			sessions = sessions!.filter((s) => s.session_id !== sessionId);
		} catch (err) {
			console.error('Failed to delete session:', err);
			alert('Failed to delete session. Please try again.');
		}
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
					<div class="session-right">
						<div class="session-questions">
							{session.question_count} question{session.question_count !== 1 ? 's' : ''}
						</div>
						<button class="delete-btn" onclick={(e) => handleDelete(e, session.session_id)} title="Delete session">
							<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
								<path d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0V6z"/>
								<path fill-rule="evenodd" d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H5.5l1-1h3l1 1H13a1 1 0 0 1 1 1v1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4H4.118zM2.5 3V2h11v1h-11z"/>
							</svg>
						</button>
					</div>
				</a>
			{/each}
		{/if}
	</div>
</main>

<style>
	.session-right {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.delete-btn {
		background: none;
		border: none;
		color: #999;
		cursor: pointer;
		padding: 0.4rem;
		border-radius: 4px;
		display: flex;
		align-items: center;
		transition: color 0.15s, background 0.15s;
	}

	.delete-btn:hover {
		color: #d32f2f;
		background: #fdecea;
	}
</style>
