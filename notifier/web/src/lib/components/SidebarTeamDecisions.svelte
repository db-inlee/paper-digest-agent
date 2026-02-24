<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { viewMode } from '$lib/stores/votes';
	import {
		teamVoteFilter,
		filteredTeamVotes,
		teamVoteLoading,
		fetchTeamVotes
	} from '$lib/stores/teamVotes';
	import type { VoteFilter } from '$lib/stores/teamVotes';

	const filters: { key: VoteFilter; label: string; emoji: string }[] = [
		{ key: 'all', label: '전체', emoji: '' },
		{ key: 'applicable', label: '적용', emoji: '🔧' },
		{ key: 'idea', label: '아이디어', emoji: '💡' },
		{ key: 'pass', label: '패스', emoji: '⏭️' }
	];

	function selectFilter(key: VoteFilter) {
		viewMode.set('team');
		teamVoteFilter.set(key);
		if ($page.url.pathname !== '/') {
			goto('/');
		}
	}

	onMount(() => {
		fetchTeamVotes();
	});
</script>

<div>
	<div class="px-3 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">
		🗳️ 팀 결정
	</div>

	<!-- Filter Tabs -->
	<div class="flex gap-1 px-3 mb-1">
		{#each filters as f}
			<button
				class="px-2 py-1 text-[11px] font-medium rounded transition-colors
						 {$viewMode === 'team' && $teamVoteFilter === f.key
							? 'bg-indigo-100 text-indigo-700'
							: 'text-gray-500 hover:bg-gray-100'}"
				on:click={() => selectFilter(f.key)}
			>
				{f.emoji} {f.label}
			</button>
		{/each}
	</div>

	<!-- Count summary -->
	{#if !$teamVoteLoading}
		<div class="px-3 py-1 text-[10px] text-gray-400">
			{$filteredTeamVotes.length}편의 투표된 논문
		</div>
	{/if}
</div>
