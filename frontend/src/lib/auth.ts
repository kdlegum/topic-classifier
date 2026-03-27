import { createClient } from '@supabase/supabase-js';
import { writable } from 'svelte/store';

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || 'https://aefhkwhqvlcbvdpoyokn.supabase.co';
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || 'sb_publishable_PBbofs1GL85HFdaMgjhCfw_2GLOiDub';

const SITE_URL: string = import.meta.env.VITE_SITE_URL || (typeof window !== 'undefined' ? window.location.origin : 'https://topictracker.co.uk');

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// Store for the current user
export const user = writable<{ email?: string } | null>(null);

// Cached session — updated by initAuth and auth state listener
let cachedSession: { access_token: string; user: { email?: string } } | null = null;
let initPromise: Promise<void> | null = null;

/**
 * Initialize auth state and subscribe to changes.
 * Only calls getSession() once; all subsequent reads use the cache.
 */
export async function initAuth() {
	if (initPromise) return initPromise;
	initPromise = (async () => {
		const { data: { session } } = await supabase.auth.getSession();
		cachedSession = session;
		user.set(session?.user ?? null);

		supabase.auth.onAuthStateChange((_event, session) => {
			cachedSession = session;
			user.set(session?.user ?? null);
		});
	})();
	return initPromise;
}

/**
 * Get the current access token from cached session
 */
export async function getAccessToken(): Promise<string | null> {
	if (initPromise) await initPromise;
	return cachedSession?.access_token ?? null;
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
	if (initPromise) await initPromise;
	return cachedSession?.user ?? null;
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
export async function signInWithMagicLink(email: string, redirectTo = SITE_URL + '/classify') {
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
export async function signInWithGoogle(redirectTo = SITE_URL + '/classify') {
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
