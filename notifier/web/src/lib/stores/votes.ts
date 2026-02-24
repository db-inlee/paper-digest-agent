import { writable, derived } from 'svelte/store';
import { browser } from '$app/environment';
import type { PaperDetail } from '$lib/types/paperDetail';

export interface Voter {
	user_id: string;
	user_name: string;
	voted_at: string;
}

export interface Paper {
	arxiv_id: string;
	arxiv_url: string;
	title: string;
	score: number;
	max_score: number;
	stars: number;
	star_emoji: string;
	summary: string;
	problem: string;
	when_to_use: string;
	when_not_to_use: string;
	github_url: string | null;
	applicable_count: number;
	idea_count: number;
	pass_count: number;
	applicable_voters: Voter[];
	idea_voters: Voter[];
	pass_voters: Voter[];
}

export interface Comment {
	id: string;
	user_name: string;
	text: string;
	created_at: string;
}

export interface SkimPaper {
	arxiv_id: string;
	arxiv_url: string;
	title: string;
	one_liner: string;
	category: string;
	matched_keywords: string[];
	applicable_count: number;
	idea_count: number;
	pass_count: number;
	applicable_voters: Voter[];
	idea_voters: Voter[];
	pass_voters: Voter[];
}

export interface ReportData {
	date: string;
	papers: Paper[];
	skim_papers: SkimPaper[];
}

// Current user name (stored in localStorage)
function createUserStore() {
	const storedName = browser ? localStorage.getItem('userName') : null;
	const { subscribe, set, update } = writable<string>(storedName || '');

	return {
		subscribe,
		set: (name: string) => {
			if (browser) {
				localStorage.setItem('userName', name);
			}
			set(name);
		}
	};
}

export const userName = createUserStore();

// Slack user ID (stored in localStorage, used for unified identity)
function createSlackUserIdStore() {
	const stored = browser ? localStorage.getItem('slackUserId') : null;
	const { subscribe, set } = writable<string>(stored || '');

	return {
		subscribe,
		set: (id: string) => {
			if (browser) {
				if (id) {
					localStorage.setItem('slackUserId', id);
				} else {
					localStorage.removeItem('slackUserId');
				}
			}
			set(id);
		}
	};
}

export const slackUserId = createSlackUserIdStore();

// View mode: 'date' = daily papers, 'team' = team decisions
export type ViewMode = 'date' | 'team';
export const viewMode = writable<ViewMode>('date');

// Available report dates
export const reportDates = writable<string[]>([]);

// Currently selected date
export const selectedDate = writable<string>('');

// Current report data
export const reportData = writable<ReportData | null>(null);

// Loading state
export const isLoading = writable<boolean>(false);

// Error state
export const error = writable<string | null>(null);

// Derived stats for the current report
export const stats = derived(reportData, ($reportData) => {
	if (!$reportData) {
		return { applicable: 0, idea: 0, pass: 0, noVote: 0, total: 0 };
	}

	let applicable = 0;
	let idea = 0;
	let pass_ = 0;
	let noVote = 0;

	for (const paper of $reportData.papers) {
		const ac = paper.applicable_count;
		const ic = paper.idea_count;
		const pc = paper.pass_count;
		if (ac === 0 && ic === 0 && pc === 0) {
			noVote++;
		} else if (ac >= ic && ac >= pc) {
			applicable++;
		} else if (ic >= ac && ic >= pc) {
			idea++;
		} else {
			pass_++;
		}
	}

	return { applicable, idea, pass: pass_, noVote, total: $reportData.papers.length };
});

// Paper detail stores
export const paperDetail = writable<PaperDetail | null>(null);
export const isDetailLoading = writable<boolean>(false);

// API functions
const API_BASE = '/api';

export async function fetchReportDates(): Promise<void> {
	isLoading.set(true);
	error.set(null);

	try {
		const response = await fetch(`${API_BASE}/reports`);
		if (!response.ok) throw new Error('Failed to fetch report dates');

		const data = await response.json();
		reportDates.set(data.dates);

		// Auto-select the first (most recent) date if none selected
		if (data.dates.length > 0) {
			selectedDate.set(data.dates[0]);
		}
	} catch (e) {
		error.set(e instanceof Error ? e.message : 'Unknown error');
	} finally {
		isLoading.set(false);
	}
}

export async function fetchReport(date: string): Promise<void> {
	isLoading.set(true);
	error.set(null);

	try {
		const response = await fetch(`${API_BASE}/reports/${date}`);
		if (!response.ok) throw new Error(`Failed to fetch report for ${date}`);

		const data = await response.json();
		reportData.set(data);
	} catch (e) {
		error.set(e instanceof Error ? e.message : 'Unknown error');
	} finally {
		isLoading.set(false);
	}
}

export async function fetchPaperDetail(arxivId: string): Promise<void> {
	isDetailLoading.set(true);
	paperDetail.set(null);

	try {
		const response = await fetch(`${API_BASE}/papers/${arxivId}`);
		if (!response.ok) throw new Error(`Failed to fetch paper detail for ${arxivId}`);

		const data: PaperDetail = await response.json();
		paperDetail.set(data);
	} catch (e) {
		error.set(e instanceof Error ? e.message : 'Unknown error');
	} finally {
		isDetailLoading.set(false);
	}
}

export async function submitVote(
	arxivId: string,
	vote: 'applicable' | 'idea' | 'pass',
	currentUserName: string,
	date: string,
	currentSlackUserId?: string
): Promise<boolean> {
	try {
		const body: Record<string, string> = {
			user_name: currentUserName,
			arxiv_id: arxivId,
			report_date: date,
			vote
		};
		if (currentSlackUserId) {
			body.slack_user_id = currentSlackUserId;
		}
		const response = await fetch(`${API_BASE}/vote`, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json'
			},
			body: JSON.stringify(body)
		});

		if (!response.ok) throw new Error('Failed to submit vote');

		// Refresh the report data to get updated votes
		await fetchReport(date);
		return true;
	} catch (e) {
		error.set(e instanceof Error ? e.message : 'Unknown error');
		return false;
	}
}

export async function fetchComments(date: string, arxivId: string): Promise<Comment[]> {
	try {
		const response = await fetch(`${API_BASE}/comments/${date}/${arxivId}`);
		if (!response.ok) throw new Error('Failed to fetch comments');
		const data = await response.json();
		return data.comments;
	} catch (e) {
		error.set(e instanceof Error ? e.message : 'Unknown error');
		return [];
	}
}

export async function submitComment(
	arxivId: string,
	date: string,
	userName: string,
	text: string
): Promise<Comment | null> {
	try {
		const response = await fetch(`${API_BASE}/comments`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				user_name: userName,
				arxiv_id: arxivId,
				report_date: date,
				text
			})
		});
		if (!response.ok) throw new Error('Failed to submit comment');
		const data = await response.json();
		return data.comment;
	} catch (e) {
		error.set(e instanceof Error ? e.message : 'Unknown error');
		return null;
	}
}

export async function deleteComment(
	date: string,
	arxivId: string,
	commentId: string,
	userName: string
): Promise<boolean> {
	try {
		const response = await fetch(`${API_BASE}/comments`, {
			method: 'DELETE',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				user_name: userName,
				report_date: date,
				arxiv_id: arxivId,
				comment_id: commentId
			})
		});
		if (!response.ok) throw new Error('Failed to delete comment');
		return true;
	} catch (e) {
		error.set(e instanceof Error ? e.message : 'Unknown error');
		return false;
	}
}
