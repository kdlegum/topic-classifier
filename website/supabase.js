
import { createClient } from "https://esm.sh/@supabase/supabase-js@2"

const SUPABASE_URL = "https://aefhkwhqvlcbvdpoyokn.supabase.co"
const SUPABASE_ANON_KEY = "sb_publishable_PBbofs1GL85HFdaMgjhCfw_2GLOiDub"

export const supabase = createClient(
  SUPABASE_URL,
  SUPABASE_ANON_KEY
)

export async function getAccessToken() {
  const {
    data: { session },
  } = await supabase.auth.getSession();

  return session?.access_token ?? null;
}

let previousUserId = null
const emailInput = document.getElementById("emailInput")
const magicLinkBtn = document.getElementById("magicLinkBtn")
const statusDisplay = document.getElementById("loginStatus")
const logoutBtn = document.getElementById("logoutBtn")
const googleBtn = document.getElementById("google-login")

function displayUser(user){
    if (user) {
        statusDisplay.textContent = `Logged in as: ${user.email}`
        magicLinkBtn.disabled = true
        logoutBtn.disabled = false
        emailInput.disabled = true
        googleBtn.disabled = true
    } else {
        statusDisplay.textContent = `Logged in as: Guest`
        magicLinkBtn.disabled = false
        logoutBtn.disabled = true
        emailInput.disabled = false
        googleBtn.disabled = false
    }
}


// check current session on page load
async function checkUser() {
  const { data: { session }, error } = await supabase.auth.getSession()
  if (error) {
    console.error("Session error:", error)
    return
  }

  const currentUserId = session?.user?.id ?? null
  if (currentUserId !== previousUserId) {
    previousUserId = currentUserId
    displayUser(session?.user ?? null)
  }
}

export function getGuestId() {
  let guestId = localStorage.getItem("guest_id");

  if (!guestId) {
    guestId = crypto.randomUUID();
    localStorage.setItem("guest_id", guestId);
  }

  return guestId;
}


// subscribe to future changes
const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
  const currentUserId = session?.user?.id ?? null
  if (currentUserId !== previousUserId) {
    previousUserId = currentUserId
    displayUser(session?.user ?? null)
  }
})

checkUser()

magicLinkBtn.addEventListener("click", async () => {
  const email = emailInput.value
  if (!email) return alert("Please enter an email!")

  magicLinkBtn.disabled = true
  googleBtn.disabled = true
  const { error } = await supabase.auth.signInWithOtp({
    email: email,
    options: {
      emailRedirectTo: window.location.href
    }
  })

  if (error) {
    console.error("Error sending magic link:", error)
    alert("Failed to send magic link. Check console.")
    magicLinkBtn.disabled = false
    googleBtn.disabled = false
  } else {
    alert("Magic link sent! Check your email.")
  }
})

logoutBtn.addEventListener("click", async () => {
  await supabase.auth.signOut()
})

googleBtn.addEventListener("click", async () => {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: "http://localhost:8000"
      }
    });

    if (error) {
      console.error("Google login error:", error);
    }
  });


