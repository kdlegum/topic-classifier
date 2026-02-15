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
 * Get paginated sessions for the current user
 */
export async function getUserSessions(page: number = 1, pageSize: number = 10) {
	const response = await apiFetch(`/user/sessions?page=${page}&page_size=${pageSize}`);

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
	has_math: boolean;
	strands: string[];
	is_reviewed?: boolean;
	creator_id?: string | null;
	description?: string | null;
	created_at?: string | null;
	topic_count?: number;
	is_selected?: boolean;
};

export type SubtopicInput = {
	subtopic_name: string;
	description: string;
};

export type TopicInput = {
	strand: string;
	topic_name: string;
	subtopics: SubtopicInput[];
};

export type SpecCreateInput = {
	qualification: string;
	subject: string;
	exam_board: string;
	spec_code: string;
	optional_modules: boolean;
	has_math: boolean;
	description?: string;
	topics: TopicInput[];
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

/**
 * Delete a session and all its related data
 */
export async function deleteSession(sessionId: string): Promise<{ detail: string }> {
	const response = await apiFetch(`/session/${sessionId}`, {
		method: 'DELETE'
	});

	if (!response.ok) {
		throw new Error(`Failed to delete session: ${response.status}`);
	}

	return response.json();
}

/**
 * Get only the user's selected specifications (for classify page)
 */
export async function getUserSpecs(): Promise<SpecInfo[]> {
	const response = await apiFetch('/user/specs');

	if (!response.ok) {
		throw new Error(`Failed to fetch user specs: ${response.status}`);
	}

	return response.json();
}

/**
 * Add a specification to the user's selections
 */
export async function addUserSpec(specCode: string): Promise<{ success: boolean }> {
	const response = await apiFetch(`/user/specs/${specCode}`, {
		method: 'POST'
	});

	if (!response.ok) {
		throw new Error(`Failed to add spec: ${response.status}`);
	}

	return response.json();
}

/**
 * Remove a specification from the user's selections
 */
export async function removeUserSpec(specCode: string): Promise<{ success: boolean }> {
	const response = await apiFetch(`/user/specs/${specCode}`, {
		method: 'DELETE'
	});

	if (!response.ok) {
		throw new Error(`Failed to remove spec: ${response.status}`);
	}

	return response.json();
}

/**
 * Create a new custom specification
 */
export async function createSpec(spec: SpecCreateInput): Promise<{ spec_code: string; success: boolean }> {
	const response = await apiFetch('/specs', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(spec)
	});

	if (!response.ok) {
		if (response.status === 409) {
			throw new Error('Specification code already exists');
		}
		throw new Error(`Failed to create spec: ${response.status}`);
	}

	return response.json();
}

/**
 * Delete a custom specification
 */
export async function deleteSpec(specCode: string): Promise<{ detail: string }> {
	const response = await apiFetch(`/specs/${specCode}`, {
		method: 'DELETE'
	});

	if (!response.ok) {
		throw new Error(`Failed to delete spec: ${response.status}`);
	}

	return response.json();
}

export type SpecDetail = SpecCreateInput & {
	creator_id?: string | null;
	is_reviewed?: boolean;
};

/**
 * Get a single spec's full data (including topics/subtopics)
 */
export async function getSpec(specCode: string): Promise<SpecDetail> {
	const response = await apiFetch(`/specs/${specCode}`);

	if (!response.ok) {
		throw new Error(`Failed to fetch spec: ${response.status}`);
	}

	return response.json();
}

/**
 * Update an existing custom specification
 */
export async function updateSpec(
	specCode: string,
	spec: SpecCreateInput
): Promise<{ spec_code: string; success: boolean }> {
	const response = await apiFetch(`/specs/${specCode}`, {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(spec)
	});

	if (!response.ok) {
		throw new Error(`Failed to update spec: ${response.status}`);
	}

	return response.json();
}

export type RevisionQuestion = {
	question_id: number;
	question_number: string;
	question_text: string;
	marks_available: number;
	original_marks_achieved: number;
	session_id: string;
	spec_code: string;
	exam_board: string;
	has_pdf: boolean;
	pdf_location: { start_page: number; start_y: number; end_page: number; end_y: number } | null;
	predictions: {
		rank: number;
		strand: string;
		topic: string;
		subtopic: string;
		spec_sub_section: string;
		similarity_score: number;
		description: string;
	}[];
	user_corrections: {
		subtopic_id: string;
		strand: string;
		topic: string;
		subtopic: string;
		spec_sub_section: string;
		description: string;
	}[];
};

export type RevisionPoolResponse = {
	total_count: number;
	spec_codes: string[];
	questions: RevisionQuestion[];
};

/**
 * Get a batch of revision-eligible questions
 */
export async function getRevisionPool(
	specCode?: string,
	limit?: number
): Promise<RevisionPoolResponse> {
	const params = new URLSearchParams();
	if (specCode) params.set('spec_code', specCode);
	if (limit) params.set('limit', String(limit));
	const qs = params.toString();

	const response = await apiFetch(`/revision/pool${qs ? `?${qs}` : ''}`);

	if (!response.ok) {
		throw new Error(`Failed to fetch revision pool: ${response.status}`);
	}

	return response.json();
}

/**
 * Record a revision attempt for a question
 */
export async function recordRevisionAttempt(
	questionId: number,
	marksAchieved: number
): Promise<{ success: boolean; is_full_marks: boolean }> {
	const response = await apiFetch(`/revision/${questionId}/attempt`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ marks_achieved: marksAchieved })
	});

	if (!response.ok) {
		throw new Error(`Failed to record revision attempt: ${response.status}`);
	}

	return response.json();
}

/**
 * Download a session's PDF as a blob
 */
export async function downloadSessionPdf(sessionId: string): Promise<Blob> {
	const response = await apiFetch(`/session/${sessionId}/pdf`);

	if (!response.ok) {
		throw new Error(`Failed to download PDF: ${response.status}`);
	}

	return response.blob();
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
