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
		const d = new Date(dateStr);
		const dd = String(d.getDate()).padStart(2, '0');
		const mm = String(d.getMonth() + 1).padStart(2, '0');
		const yy = String(d.getFullYear()).slice(2);
		return `${dd}/${mm}/${yy}`;
	}

	function getTitle(session: any): string {
		if (session.no_spec) return 'Unclassified Session';
		const parts = [session.qualification, session.subject_name].filter(Boolean);
		return parts.length > 0 ? parts.join(' ') : session.subject;
	}

	function getPaperLabel(session: any, index: number): string {
		let label: string;
		if (session.paper_number && session.paper_name) {
			label = `Paper ${session.paper_number} ${session.paper_name}`;
		} else if (session.paper_number) {
			label = `Paper ${session.paper_number}`;
		} else if (session.paper_name) {
			label = session.paper_name;
		} else {
			label = `Paper ${index + 1}`;
		}
		if (session.paper_year) {
			const series = session.paper_series
				? session.paper_series.charAt(0).toUpperCase() + session.paper_series.slice(1)
				: '';
			const suffix = [series, session.paper_year].filter(Boolean).join(' ');
			label += ` · ${suffix}`;
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

	function getStripLabel(session: any, paperLabel: string): string {
		const parts: string[] = [];
		if (session.name) parts.push(paperLabel);
		parts.push(getTitle(session));
		if (session.exam_board) parts.push(session.exam_board);
		if (session.strands?.length) parts.push(session.strands.join(', '));
		return parts.join(' · ');
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
					{@const paperLabel = getPaperLabel(session, i)}
					<a
						href="/mark_session/{session.session_id}"
						class="session-card"
						in:fly={{ y: 15, duration: 250, delay: staggerDelay(i) }}
					>
						<div class="session-header">
							<div class="session-header-left">
								{#if session.name}
									<div class="session-paper-title">{session.name}</div>
								{:else if session.no_spec}
									<div class="session-paper-title session-unclassified">Unclassified</div>
								{:else}
									<div class="session-paper-title">{paperLabel}</div>
								{/if}
							</div>
							<span class="session-date">{formatDate(session.created_at)}</span>
						</div>

						{#if !session.no_spec}
							<div class="session-strip">{getStripLabel(session, paperLabel)}</div>
						{/if}

						<div class="session-footer">
							<span class="session-questions">
								{session.question_count} question{session.question_count !== 1 ? 's' : ''}
							</span>
							<div class="session-footer-right">
								{#if session.status === 'marked'}
									{@const pct = getPct(session)}
									{#if pct !== null}
										<span class="mark-badge {pctClass(pct)}">{pct}%</span>
									{/if}
								{:else if session.status === 'in_progress'}
									<span class="status-progress">In progress</span>
								{/if}
								<button class="delete-btn" onclick={(e) => handleDelete(e, session.session_id)} title="Delete session">
									<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
										<path d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0V6z"/>
										<path fill-rule="evenodd" d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H5.5l1-1h3l1 1H13a1 1 0 0 1 1 1v1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4H4.118zM2.5 3V2h11v1h-11z"/>
									</svg>
								</button>
							</div>
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

	/* ── Lined-paper card layout (overrides global a.session-card) ── */
	a.session-card {
		flex-direction: column;
		align-items: stretch;
		padding: 0;
		gap: 0;
		overflow: hidden;
		border-left: 3px solid var(--color-primary);
	}

	.session-header {
		padding: 10px 16px 8px;
		margin-bottom: 0;
		border-bottom: none;
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 12px;
	}

	.session-header-left {
		flex: 1;
		min-width: 0;
	}

	.session-date {
		font-size: 0.78rem;
		color: var(--color-text-muted, var(--color-text-secondary));
		white-space: nowrap;
		flex-shrink: 0;
		padding-top: 2px;
	}

	.session-paper-title {
		font-weight: 700;
		font-size: 1.05rem;
		color: var(--color-text);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.session-unclassified {
		color: var(--color-text-secondary);
		font-style: italic;
	}

	/* The ruled strip — full-width band between two border lines */
	.session-strip {
		padding: 5px 16px;
		background: var(--color-surface-raised, rgba(0, 0, 0, 0.04));
		border-top: 1px solid var(--color-border);
		border-bottom: 1px solid var(--color-border);
		font-size: 0.84rem;
		color: var(--color-text-secondary);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.session-footer {
		padding: 7px 16px 10px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
	}

	.session-footer-right {
		display: flex;
		align-items: center;
		gap: 8px;
		flex-shrink: 0;
	}

	.session-questions {
		white-space: nowrap;
	}

	.status-progress {
		display: inline-flex;
		align-items: center;
		font-size: 0.82rem;
		font-weight: 600;
		color: var(--color-primary);
		background: var(--color-primary-light, rgba(0, 128, 128, 0.08));
		border: 1px solid var(--color-primary);
		padding: 2px 9px;
		border-radius: var(--radius-full);
		white-space: nowrap;
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
