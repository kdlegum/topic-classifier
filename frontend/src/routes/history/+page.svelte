<script lang="ts">
	import { onMount } from 'svelte';
	import { getUserSessions, deleteSession } from '$lib/api';

	let sessions: any[] | null = $state(null);
	let loading = $state(true);
	let error = $state(false);
	let page = $state(1);
	let total = $state(0);
	let pageSize = 10;

	$effect(() => {
		loadPage(page);
	});

	async function loadPage(p: number) {
		loading = true;
		error = false;
		try {
			const data = await getUserSessions(p, pageSize);
			sessions = data.sessions;
			total = data.total;
		} catch (err) {
			console.error('Error loading sessions:', err);
			error = true;
		} finally {
			loading = false;
		}
	}

	let totalPages = $derived(Math.max(1, Math.ceil(total / pageSize)));

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
			total -= 1;
			// If we deleted the last item on this page, go back a page
			if (sessions!.length === 1 && page > 1) {
				page -= 1;
			} else {
				await loadPage(page);
			}
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
		{:else if sessions && sessions.length === 0 && page === 1}
			<div class="empty-state">
				<p>No sessions yet.</p>
				<p><a href="/classify">Classify some questions</a> to get started!</p>
			</div>
		{:else if sessions}
			{#each sessions as session}
				<a href="/mark_session/{session.session_id}" class="session-card">
					<div class="session-info">
						<div class="session-subject">{getTitle(session)}{#if session.strands?.length} - {session.strands.join(', ')}{/if}</div>
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

			{#if totalPages > 1}
				<div class="pagination">
					<button class="page-arrow" disabled={page <= 1} onclick={() => page -= 1}>&lsaquo;</button>
					<span class="page-info">Page {page} of {totalPages}</span>
					<button class="page-arrow" disabled={page >= totalPages} onclick={() => page += 1}>&rsaquo;</button>
				</div>
			{/if}
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
		justify-content: center;
		transition: color 0.15s, background 0.15s;
	}

	.delete-btn:hover {
		color: #d32f2f;
		background: #fdecea;
	}

	.session-questions {
		white-space: nowrap;
	}

	.pagination {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.75rem;
		margin-top: 1.5rem;
		padding: 0.75rem 0;
	}

	.page-arrow {
		background: none;
		border: none;
		cursor: pointer;
		font-size: 1.4rem;
		line-height: 1;
		padding: 0.2rem 0.4rem;
		color: #555;
		border-radius: 4px;
		transition: color 0.15s, background 0.15s;
	}

	.page-arrow:hover:not(:disabled) {
		color: #0077cc;
		background: #f0f6ff;
	}

	.page-arrow:disabled {
		opacity: 0.3;
		cursor: not-allowed;
	}

	.page-info {
		font-size: 0.85rem;
		color: #666;
		white-space: nowrap;
		min-width: max-content;
	}
</style>
