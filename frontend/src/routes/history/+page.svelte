<script lang="ts">
	import { onMount } from 'svelte';
	import { fly, fade, scale } from 'svelte/transition';
	import { getUserSessions, deleteSession } from '$lib/api';
	import { shouldAnimate, DURATIONS } from '$lib/motion';

	let sessions: any[] | null = $state(null);
	let loading = $state(true);
	let error = $state(false);
	let page = $state(1);
	let total = $state(0);
	let pageSize = 10;
	let ready = $state(false);
	let deletingId: string | null = $state(null);

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
			ready = true;
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
		if (session.no_spec) return 'Unclassified Session';
		const parts = [session.qualification, session.subject_name].filter(Boolean);
		return parts.length > 0 ? parts.join(' ') : session.subject;
	}

	function getPaperLabel(session: any): string | null {
		if (!session.paper_number) return null;
		let label = `Paper ${session.paper_number}`;
		if (session.paper_name) label += ` ${session.paper_name}`;
		if (session.paper_year) {
			const series = session.paper_series
				? session.paper_series.charAt(0).toUpperCase() + session.paper_series.slice(1)
				: '';
			label += ` · ${series} ${session.paper_year}`.trim();
		}
		return label;
	}

	async function handleDelete(e: Event, sessionId: string) {
		e.preventDefault();
		e.stopPropagation();
		if (!confirm('Are you sure you want to delete this session? This cannot be undone.')) return;
		deletingId = sessionId;
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
		} finally {
			deletingId = null;
		}
	}

	function staggerDelay(i: number): number {
		return shouldAnimate() ? 50 + i * DURATIONS.stagger : 0;
	}

	function getPct(session: any): number | null {
		if (session.status !== 'marked') return null;
		if (!session.total_marks_available) return null;
		return Math.round((session.total_marks_achieved / session.total_marks_available) * 100);
	}

	function pctClass(pct: number): string {
		if (pct >= 70) return 'pct-high';
		if (pct >= 40) return 'pct-mid';
		return 'pct-low';
	}
</script>

<svelte:head>
	<title>My Sessions - Topic Tracker</title>
</svelte:head>

<main class="page-content">
	{#if !ready}
		<div class="loading">
			<span class="loading-spinner"></span>
			Loading sessions...
		</div>
	{:else}
		<div in:fly={{ y: 20, duration: 300 }}>
			<h1>My Sessions</h1>
			<p class="page-subtitle">View your past classification sessions.</p>
		</div>

	<div class="sessions-list">
		{#if loading}
			<div class="loading">
				<span class="loading-spinner"></span>
				Loading sessions...
			</div>
		{:else if error}
			<div class="error-state" in:fade={{ duration: 200 }}>
				<p>Failed to load sessions. Please try again.</p>
			</div>
		{:else if sessions && sessions.length === 0 && page === 1}
			<div class="empty-state" in:fade={{ duration: 200 }}>
				<p>No sessions yet.</p>
				<p><a href="/classify">Classify some questions</a> to get started!</p>
			</div>
		{:else if sessions}
			{#each sessions as session, i (session.session_id)}
				<a
					href="/mark_session/{session.session_id}"
					class="session-card"
					in:fly={{ y: 15, duration: 250, delay: staggerDelay(i) }}
				>
					<div class="session-info">
						{#if session.name}
							<div class="session-custom-name">{session.name}</div>
							<div class="session-subject session-subject-secondary">{getTitle(session)}{#if session.strands?.length} - {session.strands.join(', ')}{/if}</div>
						{:else}
							<div class="session-subject">{getTitle(session)}{#if session.strands?.length} - {session.strands.join(', ')}{/if}</div>
						{/if}
						<div class="session-meta">
							{#if session.no_spec}
						<span class="session-board no-spec-badge">No specification</span>
					{:else}
						<span class="session-board">{session.exam_board}</span>
					{/if}
							{@const paperLabel = getPaperLabel(session)}
							{#if paperLabel}
								<span class="session-paper">{paperLabel}</span>
							{/if}
							<span class="session-date">{formatDate(session.created_at)}</span>
						</div>
					</div>
					<div class="session-right">
						<div class="session-questions">
							{session.question_count} question{session.question_count !== 1 ? 's' : ''}
						</div>
						{#if session.status === 'marked'}
							{@const pct = getPct(session)}
							{#if pct !== null}
								<span class="mark-badge {pctClass(pct)}">{pct}%</span>
							{/if}
						{:else if session.status === 'in_progress'}
							<span class="mark-badge pct-progress">In progress</span>
						{/if}
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
				<div class="pagination" in:fade={{ duration: 200 }}>
					<button class="page-arrow" disabled={page <= 1} onclick={() => page -= 1}>&lsaquo;</button>
					<span class="page-info">Page {page} of {totalPages}</span>
					<button class="page-arrow" disabled={page >= totalPages} onclick={() => page += 1}>&rsaquo;</button>
				</div>
			{/if}
		{/if}
	</div>
	{/if}
</main>

<style>
	.page-subtitle {
		color: var(--color-text-secondary);
		font-size: 1.02rem;
		margin-bottom: 8px;
	}

	.no-spec-badge {
		color: var(--color-text-muted);
		font-style: italic;
	}

	.loading-spinner {
		display: inline-block;
		width: 18px;
		height: 18px;
		border: 2.5px solid var(--color-border);
		border-top-color: var(--color-primary);
		border-radius: 50%;
		animation: spin 0.7s linear infinite;
		vertical-align: middle;
		margin-right: 8px;
	}

	@keyframes spin {
		to { transform: rotate(360deg); }
	}

	.session-right {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}

	.delete-btn {
		background: none;
		border: none;
		color: var(--color-text-muted);
		cursor: pointer;
		padding: 0.4rem;
		border-radius: var(--radius-sm);
		display: flex;
		align-items: center;
		justify-content: center;
		transition: color var(--transition-fast), background var(--transition-fast);
	}

	.delete-btn:hover {
		color: var(--color-error);
		background: var(--color-error-bg);
	}

	.session-questions {
		white-space: nowrap;
	}

	.session-custom-name {
		font-weight: 600;
		font-size: 1rem;
		color: var(--color-text);
	}

	.session-subject-secondary {
		font-size: 0.85rem;
		color: var(--color-text-secondary);
	}

	.session-paper {
		font-size: 0.82rem;
		color: var(--color-text-secondary);
		background: var(--color-surface-raised, var(--color-border));
		padding: 1px 7px;
		border-radius: var(--radius-full);
		white-space: nowrap;
	}

	.mark-badge {
		display: inline-flex;
		align-items: center;
		padding: 3px 10px;
		border-radius: var(--radius-full);
		font-size: 0.82rem;
		font-weight: 700;
		white-space: nowrap;
	}

	.pct-high { background: var(--color-success-bg); color: #15803d; }
	.pct-mid  { background: var(--color-warning-bg); color: #b45309; }
	.pct-low  { background: var(--color-error-bg);   color: #b91c1c; }
	.pct-progress { background: var(--color-warning-bg); color: #b45309; }

	.pagination {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.75rem;
		margin-top: 1.5rem;
		padding: 0.75rem 0;
	}

	.page-arrow {
		background: var(--color-surface);
		border: 1.5px solid var(--color-border);
		cursor: pointer;
		font-size: 1.4rem;
		line-height: 1;
		padding: 0.3rem 0.6rem;
		color: var(--color-text-secondary);
		border-radius: var(--radius-sm);
		transition: color var(--transition-fast), background var(--transition-fast), border-color var(--transition-fast);
	}

	.page-arrow:hover:not(:disabled) {
		color: var(--color-primary);
		border-color: var(--color-primary);
		background: var(--color-primary-light);
	}

	.page-arrow:disabled {
		opacity: 0.3;
		cursor: not-allowed;
	}

	.page-info {
		font-size: 0.85rem;
		color: var(--color-text-secondary);
		white-space: nowrap;
		min-width: max-content;
	}
</style>
