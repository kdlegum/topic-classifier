import { getAccessToken, getGuestId } from "./auth.js";

const API_BASE = window.location.origin;

/**
 * Make an authenticated API request
 * Automatically adds auth headers (Bearer token and/or guest ID)
 */
export async function apiFetch(endpoint, options = {}) {
  const token = await getAccessToken();
  const guestId = getGuestId();

  const headers = {
    ...options.headers,
    ...(token && { Authorization: `Bearer ${token}` }),
    "X-Guest-ID": guestId,
  };

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  return response;
}

/**
 * Get all sessions for the current user (or guest)
 */
export async function getUserSessions() {
  const response = await apiFetch("/user/sessions");
  if (!response.ok) {
    throw new Error(`Failed to fetch sessions: ${response.status}`);
  }
  return response.json();
}

/**
 * Get a specific session by ID
 */
export async function getSession(sessionId) {
  const response = await apiFetch(`/session/${sessionId}`);
  if (!response.ok) {
    if (response.status === 403) {
      throw new Error("Not authorized to view this session");
    }
    if (response.status === 404) {
      throw new Error("Session not found");
    }
    throw new Error(`Failed to fetch session: ${response.status}`);
  }
  return response.json();
}

/**
 * Classify questions against a specification
 */
export async function classifyQuestions(questions, specCode) {
  const response = await apiFetch("/classify/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      question_text: questions,
      SpecCode: specCode,
    }),
  });

  if (!response.ok) {
    throw new Error(`Classification failed: ${response.status}`);
  }

  return response.json();
}

/**
 * Upload a PDF for classification
 */
export async function uploadPdf(file, specCode) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await apiFetch(`/upload-pdf/${specCode}`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Upload failed: ${response.status}`);
  }

  return response.json();
}

/**
 * Get PDF processing status
 */
export async function getPdfStatus(jobId) {
  const response = await fetch(`${API_BASE}/upload-pdf-status/${jobId}`);
  if (!response.ok) {
    throw new Error(`Status check failed: ${response.status}`);
  }
  return response.json();
}

/**
 * Migrate guest sessions to authenticated user account
 * Call this after a user signs up/logs in
 */
export async function migrateGuestSessions() {
  const response = await apiFetch("/migrate-guest-sessions", {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(`Migration failed: ${response.status}`);
  }

  return response.json();
}

/**
 * Update the marks of a list of questions for a given session
 * @param {string} sessionId - The session ID
 * @param {Array<{question_id: number, marks_achieved: number}>} marksObjectList - List of marks to update
 * @returns {Promise<{success: boolean, total_marks_available: number, total_marks_achieved: number}>}
 */
export async function uploadAchievedMarks(sessionId, marksObjectList) {
  const response = await apiFetch(`/session/${sessionId}/marks`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ marks: marksObjectList }),
  });

  if (!response.ok) {
    throw new Error(`Mark Upload failed: ${response.status}`);
  }

  return response.json();
}