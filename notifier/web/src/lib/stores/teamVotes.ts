import { writable, derived } from 'svelte/store';

export interface TeamVotePaper {
	arxiv_id: string;
	title: string;
	date: string;
	applicable_count: number;
	idea_count: number;
	pass_count: number;
	dominant_vote: 'applicable' | 'idea' | 'pass';
}

export type VoteFilter = 'all' | 'applicable' | 'idea' | 'pass';

export const teamVotePapers = writable<TeamVotePaper[]>([]);
export const teamVoteFilter = writable<VoteFilter>('all');
export const teamDateFilter = writable<string>('all');
export const teamVoteLoading = writable<boolean>(false);

// Unique dates from voted papers (newest first)
export const teamDates = derived(teamVotePapers, ($papers) => {
	const dates = [...new Set($papers.map((p) => p.date))];
	dates.sort((a, b) => b.localeCompare(a));
	return dates;
});

export const filteredTeamVotes = derived(
	[teamVotePapers, teamVoteFilter, teamDateFilter],
	([$papers, $filter, $dateFilter]) => {
		let result = $papers;
		if ($filter !== 'all') {
			result = result.filter((p) => p.dominant_vote === $filter);
		}
		if ($dateFilter !== 'all') {
			result = result.filter((p) => p.date === $dateFilter);
		}
		return result;
	}
);

const API_BASE = '/api';

export async function fetchTeamVotes(): Promise<void> {
	teamVoteLoading.set(true);
	try {
		const response = await fetch(`${API_BASE}/votes/all`);
		if (!response.ok) throw new Error('Failed to fetch team votes');
		const data = await response.json();
		teamVotePapers.set(data.papers);
	} catch {
		teamVotePapers.set([]);
	} finally {
		teamVoteLoading.set(false);
	}
}
