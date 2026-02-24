import { writable } from 'svelte/store';

export interface CustomKeyword {
	keyword: string;
	source: 'manual' | 'arxiv' | 'freetext';
	added_at: string;
	added_by: string;
	source_detail: string | null;
}

export interface TopicsData {
	default_keywords: string[];
	custom_keywords: CustomKeyword[];
	disabled_default_keywords: string[];
	effective_keywords: string[];
}

export const topicsData = writable<TopicsData | null>(null);
export const topicsLoading = writable<boolean>(false);
export const topicsError = writable<string | null>(null);

const API_BASE = '/api';

export async function fetchTopics(): Promise<void> {
	topicsLoading.set(true);
	topicsError.set(null);

	try {
		const response = await fetch(`${API_BASE}/topics`);
		if (!response.ok) throw new Error('Failed to fetch topics');
		const data: TopicsData = await response.json();
		topicsData.set(data);
	} catch (e) {
		topicsError.set(e instanceof Error ? e.message : 'Unknown error');
	} finally {
		topicsLoading.set(false);
	}
}

export async function addKeywords(
	keywords: string[],
	source: 'manual' | 'arxiv' | 'freetext' = 'manual',
	addedBy: string = '',
	sourceDetail: string | null = null
): Promise<boolean> {
	try {
		const response = await fetch(`${API_BASE}/topics/add`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				keywords,
				source,
				added_by: addedBy,
				source_detail: sourceDetail
			})
		});
		if (!response.ok) throw new Error('Failed to add keywords');
		await fetchTopics();
		return true;
	} catch (e) {
		topicsError.set(e instanceof Error ? e.message : 'Unknown error');
		return false;
	}
}

export async function removeKeyword(keyword: string): Promise<boolean> {
	try {
		const response = await fetch(`${API_BASE}/topics/remove`, {
			method: 'DELETE',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ keyword })
		});
		if (!response.ok) throw new Error('Failed to remove keyword');
		await fetchTopics();
		return true;
	} catch (e) {
		topicsError.set(e instanceof Error ? e.message : 'Unknown error');
		return false;
	}
}

export async function toggleDefaultKeyword(keyword: string): Promise<boolean> {
	try {
		const response = await fetch(`${API_BASE}/topics/toggle-default`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ keyword })
		});
		if (!response.ok) throw new Error('Failed to toggle keyword');
		await fetchTopics();
		return true;
	} catch (e) {
		topicsError.set(e instanceof Error ? e.message : 'Unknown error');
		return false;
	}
}

export async function extractFromArxiv(
	arxivId: string
): Promise<{ title: string; keywords: string[] } | null> {
	try {
		const response = await fetch(`${API_BASE}/topics/extract-arxiv`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ arxiv_id: arxivId })
		});
		if (!response.ok) {
			const err = await response.json().catch(() => ({}));
			throw new Error(err.detail || 'Failed to extract from arXiv');
		}
		return await response.json();
	} catch (e) {
		topicsError.set(e instanceof Error ? e.message : 'Unknown error');
		return null;
	}
}

export async function extractFromText(
	text: string
): Promise<{ keywords: string[] } | null> {
	try {
		const response = await fetch(`${API_BASE}/topics/extract-text`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ text })
		});
		if (!response.ok) {
			const err = await response.json().catch(() => ({}));
			throw new Error(err.detail || 'Failed to extract from text');
		}
		return await response.json();
	} catch (e) {
		topicsError.set(e instanceof Error ? e.message : 'Unknown error');
		return null;
	}
}
