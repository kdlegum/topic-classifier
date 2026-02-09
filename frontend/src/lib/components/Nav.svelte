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
	let userDisplay = $derived($user ? $user.email : 'Guest');
</script>

<nav class="main-nav">
	<div class="nav-brand">
		<a href="/classify">Topic Tracker</a>
	</div>
	<div class="nav-links">
		<a href="/classify" class:active={isClassify}>Classify</a>
		<a href="/specs" class:active={isSpecs}>Specs</a>
		<a href="/history" class:active={isHistory}>My Sessions</a>
		<a href="/analytics" class:active={isAnalytics}>Analytics</a>
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
		background: #333;
		color: white;
	}

	.nav-brand {
		flex: 1;
	}

	.nav-brand a {
		color: white;
		text-decoration: none;
		font-size: 1.2rem;
		font-weight: bold;
	}

	.nav-links {
		display: flex;
		gap: 24px;
	}

	.nav-links a {
		color: #ccc;
		text-decoration: none;
		padding: 8px 0;
		border-bottom: 2px solid transparent;
	}

	.nav-links a:hover {
		color: white;
	}

	.nav-links a.active {
		color: white;
		border-bottom-color: #0077cc;
	}

	.nav-user {
		flex: 1;
		display: flex;
		align-items: center;
		justify-content: flex-end;
		gap: 16px;
	}

	.user-display {
		color: #aaa;
		font-size: 0.9rem;
	}

	.nav-btn {
		color: white;
		text-decoration: none;
		padding: 6px 12px;
		border: 1px solid #666;
		border-radius: 4px;
	}

	.nav-btn:hover {
		background: #444;
	}

	@media (max-width: 700px) {
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
			gap: 16px;
			padding-top: 8px;
		}

		.user-display {
			display: none;
		}
	}
</style>
