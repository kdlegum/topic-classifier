<script lang="ts">
	import { page } from '$app/stores';
	import { user, signOut } from '$lib/auth';

	async function handleLogout(e: Event) {
		e.preventDefault();
		await signOut();
		window.location.href = '/';
	}

	let currentPath = $derived($page.url.pathname);
	let isClassify = $derived(currentPath === '/classify');
	let isSpecs = $derived(currentPath.startsWith('/specs'));
	let isHistory = $derived(currentPath === '/history');
	let isAnalytics = $derived(currentPath === '/analytics');
	let isRevision = $derived(currentPath === '/revision');
	let userDisplay = $derived($user ? $user.email : 'Guest');
</script>

<nav class="main-nav">
	<div class="nav-brand">
		<a href="/classify">Topic Tracker</a>
	</div>
	<div class="nav-links">
		<a href="/classify" class:active={isClassify}>Classify</a>
		<a href="/specs" class:active={isSpecs}>Specs</a>
		<a href="/history" class:active={isHistory}><span class="shorten-text">My&nbsp;</span>Sessions</a>
		<a href="/analytics" class:active={isAnalytics}>Analytics</a>
		<a href="/revision" class:active={isRevision}>Revision</a>
	</div>
	<div class="nav-user">
		<span class="user-display">{userDisplay}</span>
		{#if $user}
			<a href="#logout" onclick={handleLogout} class="nav-btn">Log out</a>
		{:else}
			<a href="/" class="nav-btn">Log in</a>
		{/if}
	</div>
</nav>

<style>
	.main-nav {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 12px 24px;
		background: #1C1917;
		color: white;
		font-family: var(--font-body);
	}

	.nav-brand {
		flex: 1;
	}

	.nav-brand a {
		color: white;
		text-decoration: none;
		font-size: 1.2rem;
		font-weight: 700;
		font-family: var(--font-heading);
		letter-spacing: -0.02em;
	}

	.nav-links {
		display: flex;
		gap: 6px;
	}

	.nav-links a {
		color: #A8A29E;
		text-decoration: none;
		padding: 8px 14px;
		border-radius: var(--radius-sm);
		font-weight: 600;
		font-size: 0.92rem;
		transition: color var(--transition-fast), background var(--transition-fast);
	}

	.nav-links a:hover {
		color: white;
		background: rgba(255, 255, 255, 0.08);
	}

	.nav-links a.active {
		color: white;
		background: var(--color-primary);
	}

	.nav-user {
		flex: 1;
		display: flex;
		align-items: center;
		justify-content: flex-end;
		gap: 16px;
	}

	.user-display {
		color: #78716C;
		font-size: 0.88rem;
		font-weight: 500;
	}

	.nav-btn {
		color: white;
		text-decoration: none;
		padding: 6px 14px;
		border: 1.5px solid #44403C;
		border-radius: var(--radius-sm);
		white-space: nowrap;
		font-size: 0.88rem;
		font-weight: 600;
		transition: background var(--transition-fast), border-color var(--transition-fast);
	}

	.nav-btn:hover {
		background: #292524;
		border-color: #57534E;
	}

	@media (max-width: 1100px) {
		.user-display {
			display: none;
		}
	}

	@media (max-width: 700px) {
		.shorten-text {
			display: none;
		}

		.main-nav {
			flex-wrap: wrap;
			padding: 10px 16px;
		}

		.nav-brand {
			flex: none;
		}

		.nav-user {
			flex: none;
		}

		.nav-links {
			order: 3;
			width: 100%;
			justify-content: center;
			gap: 4px;
			padding-top: 10px;
			font-size: 0.85rem;
		}

		.nav-links a {
			padding: 6px 10px;
			font-size: 0.85rem;
		}

		.user-display {
			display: none;
		}
	}
</style>
