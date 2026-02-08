import { getAccessToken, getGuestId } from './auth';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

/**
 * Make an authenticated API request
 * Automatically adds auth headers (Bearer token and/or guest ID)
 */
export async function apiFetch(endpoint: string, options: RequestInit = {}): Promise<Response> {
	const token = await getAccessToken();
	const guestId = getGuestId();

	const headers: HeadersInit = {
		...options.headers,
		...(token && { Authorization: `Bearer ${token}` }),
		'X-Guest-ID': guestId
	};

	const response = await fetch(`${API_BASE}${endpoint}`, {
		...options,
		headers
	});

	return response;
}

/**
 * Migrate guest sessions to authenticated user account
 * Call this after a user signs up/logs in
 */
export async function migrateGuestSessions(): Promise<{ migrated: number }> {
	const response = await apiFetch('/migrate-guest-sessions', {
		method: 'POST'
	});

	if (!response.ok) {
		throw new Error(`Migration failed: ${response.status}`);
	}

	return response.json();
}

/**
 * Classify questions against a specification
 */
export async function classifyQuestions(
	questions: string[],
	specCode: string,
	strands?: string[]
): Promise<{ session_id: string }> {
	const questionObjects = questions.map((text) => ({ text, marks: null }));

	const body: Record<string, unknown> = {
		question_object: questionObjects,
		SpecCode: specCode
	};
	if (strands && strands.length > 0) {
		body.strands = strands;
	}

	const response = await apiFetch('/classify/', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body)
	});

	if (!response.ok) {
		throw new Error(`Classification failed: ${response.status}`);
	}

	return response.json();
}

/**
 * Upload a PDF for processing
 */
export async function uploadPdf(
	file: File,
	specCode: string,
	strands?: string[]
): Promise<{ job_id: string }> {
	const formData = new FormData();
	formData.append('file', file);

	let endpoint = `/upload-pdf/${specCode}`;
	if (strands && strands.length > 0) {
		endpoint += `?strands=${encodeURIComponent(strands.join(','))}`;
	}

	const response = await apiFetch(endpoint, {
		method: 'POST',
		body: formData
	});

	if (!response.ok) {
		throw new Error(`PDF upload failed: ${response.status}`);
	}

	return response.json();
}

/**
 * Check PDF processing status
 */
export async function getPdfStatus(
	jobId: string
): Promise<{ job_id: string; status: string; session_id: string | null }> {
	const response = await apiFetch(`/upload-pdf-status/${jobId}`);

	if (!response.ok) {
		throw new Error(`Status check failed: ${response.status}`);
	}

	return response.json();
}

/**
 * Get session details by ID
 */
export async function getSession(sessionId: string) {
	const response = await apiFetch(`/session/${sessionId}`);

	if (!response.ok) {
		throw new Error(`${response.status}`);
	}

	return response.json();
}

/**
 * Upload achieved marks for questions in a session
 */
export async function uploadAchievedMarks(
	sessionId: string,
	marks: { question_id: number; marks_achieved: number }[]
): Promise<{ success: boolean }> {
	const response = await apiFetch(`/session/${sessionId}/marks`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ marks })
	});

	if (!response.ok) {
		throw new Error(`Failed to save marks: ${response.status}`);
	}

	return response.json();
}

/**
 * Update question text and/or marks available
 */
export async function updateQuestion(
	sessionId: string,
	questionId: number,
	data: { question_text?: string; marks_available?: number }
): Promise<{ question_id: number; question_text: string; marks_available: number | null }> {
	const response = await apiFetch(`/session/${sessionId}/question/${questionId}`, {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data)
	});

	if (!response.ok) {
		throw new Error(`Failed to update question: ${response.status}`);
	}

	return response.json();
}

/**
 * Get all sessions for the current user
 */
export async function getUserSessions() {
	const response = await apiFetch('/user/sessions');

	if (!response.ok) {
		throw new Error(`Failed to fetch sessions: ${response.status}`);
	}

	return response.json();
}

/**
 * Get topic hierarchy for a specification (strand -> topic -> subtopic)
 */
export async function getTopicHierarchy(specCode: string) {
	const response = await apiFetch(`/topics/${specCode}/hierarchy`);

	if (!response.ok) {
		throw new Error(`Failed to fetch topic hierarchy: ${response.status}`);
	}

	return response.json();
}

/**
 * Save user topic corrections for questions in a session
 */
/**
 * Get analytics summary for the current user
 */
export async function getAnalyticsSummary() {
	const response = await apiFetch('/analytics/summary');

	if (!response.ok) {
		throw new Error(`Failed to fetch analytics: ${response.status}`);
	}

	return response.json();
}

/**
 * Save user topic corrections for questions in a session
 */
/**
 * Get subtopic progress/mastery for a specification
 */
export async function getProgress(specCode: string) {
	const response = await apiFetch(`/progress/${specCode}`);

	if (!response.ok) {
		throw new Error(`Failed to fetch progress: ${response.status}`);
	}

	return response.json();
}

export type SpecInfo = {
	spec_code: string;
	subject: string;
	exam_board: string;
	qualification: string;
	optional_modules: boolean;
	strands: string[];
};

/**
 * Get all specifications with strands and optional_modules flag
 */
export async function getSpecs(): Promise<SpecInfo[]> {
	const response = await apiFetch('/specs');

	if (!response.ok) {
		throw new Error(`Failed to fetch specs: ${response.status}`);
	}

	return response.json();
}

/**
 * Get user's saved module selections for a spec
 */
export async function getUserModules(
	specCode: string
): Promise<{ spec_code: string; selected_strands: string[] }> {
	const response = await apiFetch(`/user/modules/${specCode}`);

	if (!response.ok) {
		throw new Error(`Failed to fetch user modules: ${response.status}`);
	}

	return response.json();
}

/**
 * Save user's module selections for a spec (full replacement)
 */
export async function saveUserModules(
	specCode: string,
	strands: string[]
): Promise<{ success: boolean }> {
	const response = await apiFetch(`/user/modules/${specCode}`, {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ strands })
	});

	if (!response.ok) {
		throw new Error(`Failed to save user modules: ${response.status}`);
	}

	return response.json();
}

export async function saveUserCorrections(
	sessionId: string,
	corrections: { question_id: number; subtopic_ids: string[] }[]
): Promise<{ success: boolean }> {
	const response = await apiFetch(`/session/${sessionId}/corrections`, {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ corrections })
	});

	if (!response.ok) {
		throw new Error(`Failed to save corrections: ${response.status}`);
	}

	return response.json();
}
