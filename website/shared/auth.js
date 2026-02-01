import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const SUPABASE_URL = "https://aefhkwhqvlcbvdpoyokn.supabase.co";
const SUPABASE_ANON_KEY = "sb_publishable_PBbofs1GL85HFdaMgjhCfw_2GLOiDub";

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

/**
 * Get the current access token from Supabase session
 */
export async function getAccessToken() {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session?.access_token ?? null;
}

/**
 * Get or create a guest ID stored in localStorage
 */
export function getGuestId() {
  let guestId = localStorage.getItem("guest_id");
  if (!guestId) {
    guestId = crypto.randomUUID();
    localStorage.setItem("guest_id", guestId);
  }
  return guestId;
}

/**
 * Get the current authenticated user (or null if not logged in)
 */
export async function getCurrentUser() {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session?.user ?? null;
}

/**
 * Check if user is authenticated
 */
export async function isAuthenticated() {
  const user = await getCurrentUser();
  return user !== null;
}

/**
 * Redirect to login page if not authenticated
 */
export async function requireAuth(redirectUrl = "/") {
  const authenticated = await isAuthenticated();
  if (!authenticated) {
    window.location.href = redirectUrl;
    return false;
  }
  return true;
}

/**
 * Subscribe to auth state changes
 */
export function onAuthChange(callback) {
  return supabase.auth.onAuthStateChange((_event, session) => {
    callback(session?.user ?? null, _event);
  });
}

/**
 * Sign in with magic link (email OTP)
 */
export async function signInWithMagicLink(email, redirectTo = window.location.origin + "/classify") {
  const { error } = await supabase.auth.signInWithOtp({
    email,
    options: {
      emailRedirectTo: redirectTo,
    },
  });
  return { error };
}

/**
 * Sign in with Google OAuth
 */
export async function signInWithGoogle(redirectTo = window.location.origin + "/classify") {
  const { error } = await supabase.auth.signInWithOAuth({
    provider: "google",
    options: {
      redirectTo,
    },
  });
  return { error };
}

/**
 * Sign out
 */
export async function signOut() {
  await supabase.auth.signOut();
}
