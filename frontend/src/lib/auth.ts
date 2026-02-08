import { createClient } from '@supabase/supabase-js';
import { writable } from 'svelte/store';

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || 'https://aefhkwhqvlcbvdpoyokn.supabase.co';
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || 'sb_publishable_PBbofs1GL85HFdaMgjhCfw_2GLOiDub';

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// Store for the current user
export const user = writable<{ email?: string } | null>(null);

/**
 * Initialize auth state and subscribe to changes
 */
export async function initAuth() {
	const { data: { session } } = await supabase.auth.getSession();
	user.set(session?.user ?? null);

	supabase.auth.onAuthStateChange((_event, session) => {
		user.set(session?.user ?? null);
	});
}

/**
 * Get the current access token from Supabase session
 */
export async function getAccessToken(): Promise<string | null> {
	const { data: { session } } = await supabase.auth.getSession();
	return session?.access_token ?? null;
}

/**
 * Get or create a guest ID stored in localStorage
 */
export function getGuestId(): string {
	if (typeof localStorage === 'undefined') return '';
	let guestId = localStorage.getItem('guest_id');
	if (!guestId) {
		guestId = crypto.randomUUID();
		localStorage.setItem('guest_id', guestId);
	}
	return guestId;
}

/**
 * Get the current authenticated user (or null if not logged in)
 */
export async function getCurrentUser() {
	const { data: { session } } = await supabase.auth.getSession();
	return session?.user ?? null;
}

/**
 * Check if user is authenticated
 */
export async function isAuthenticated(): Promise<boolean> {
	const currentUser = await getCurrentUser();
	return currentUser !== null;
}

/**
 * Sign in with magic link (email OTP)
 */
export async function signInWithMagicLink(email: string, redirectTo = window.location.origin + '/classify') {
	const { error } = await supabase.auth.signInWithOtp({
		email,
		options: {
			emailRedirectTo: redirectTo
		}
	});
	return { error };
}

/**
 * Sign in with Google OAuth
 */
export async function signInWithGoogle(redirectTo = window.location.origin + '/classify') {
	const { error } = await supabase.auth.signInWithOAuth({
		provider: 'google',
		options: {
			redirectTo
		}
	});
	return { error };
}

/**
 * Sign out
 */
export async function signOut() {
	await supabase.auth.signOut();
}
