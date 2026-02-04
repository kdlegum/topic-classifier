<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import {
		getCurrentUser,
		signInWithMagicLink,
		signInWithGoogle,
		supabase
	} from '$lib/auth';
	import { migrateGuestSessions } from '$lib/api';

	let email = '';
	let statusMessage = '';
	let isLoading = false;

	onMount(() => {
		// Check if already logged in
		checkExistingSession();

		// Listen for auth state changes (e.g., after magic link callback)
		const { data: { subscription } } = supabase.auth.onAuthStateChange(async (event, session) => {
			if (session?.user && event === 'SIGNED_IN') {
				statusMessage = 'Logged in! Migrating sessions...';
				try {
					const result = await migrateGuestSessions();
					if (result.migrated > 0) {
						statusMessage = `Migrated ${result.migrated} session(s). Redirecting...`;
					}
				} catch (e) {
					console.error('Migration error:', e);
				}
				goto('/classify');
			}
		});

		return () => {
			subscription.unsubscribe();
		};
	});

	async function checkExistingSession() {
		const user = await getCurrentUser();
		if (user) {
			try {
				await migrateGuestSessions();
			} catch (e) {
				console.error('Migration error:', e);
			}
			goto('/classify');
		}
	}

	async function handleMagicLink() {
		const trimmedEmail = email.trim();
		if (!trimmedEmail) {
			alert('Please enter an email!');
			return;
		}

		isLoading = true;
		statusMessage = 'Sending magic link...';

		const { error } = await signInWithMagicLink(trimmedEmail);

		if (error) {
			console.error('Error sending magic link:', error);
			statusMessage = 'Failed to send magic link. Please try again.';
			isLoading = false;
		} else {
			statusMessage = 'Magic link sent! Check your email.';
		}
	}

	async function handleGoogleLogin() {
		isLoading = true;
		statusMessage = 'Redirecting to Google...';

		const { error } = await signInWithGoogle();

		if (error) {
			console.error('Google login error:', error);
			statusMessage = 'Google login failed. Please try again.';
			isLoading = false;
		}
	}
</script>

<svelte:head>
	<title>Login - Topic Tracker</title>
</svelte:head>

<div class="login-container">
	<h1>Topic Tracker</h1>
	<p class="subtitle">Classify exam questions by topic</p>

	<div class="login-box">
		<div class="section">
			<label for="emailInput">Email</label>
			<input
				type="email"
				id="emailInput"
				placeholder="Enter your email"
				bind:value={email}
				disabled={isLoading}
			/>
		</div>

		<div class="section">
			<button
				class="btn-primary"
				on:click={handleMagicLink}
				disabled={isLoading}
			>
				Send Login Link
			</button>
		</div>

		<div class="divider">
			<span>or</span>
		</div>

		<div class="section">
			<button
				class="btn-google"
				on:click={handleGoogleLogin}
				disabled={isLoading}
			>
				Sign in with Google
			</button>
		</div>

		<div class="section guest-link">
			<a href="/classify">Continue as Guest</a>
		</div>
	</div>

	{#if statusMessage}
		<div class="login-status">{statusMessage}</div>
	{/if}
</div>
