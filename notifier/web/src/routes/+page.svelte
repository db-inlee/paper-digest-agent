<script lang="ts">
	import { onMount } from 'svelte';
	import {
		reportDates,
		selectedDate,
		reportData,
		isLoading,
		error,
		stats,
		viewMode,
		fetchReportDates,
		fetchReport
	} from '$lib/stores/votes';
	import type { SkimPaper } from '$lib/stores/votes';
	import {
		filteredTeamVotes,
		teamVoteLoading,
		teamVoteFilter,
		teamDateFilter,
		teamDates,
		fetchTeamVotes
	} from '$lib/stores/teamVotes';
	import type { VoteFilter } from '$lib/stores/teamVotes';
	import PaperCard from '$lib/components/PaperCard.svelte';
	import VoteButton from '$lib/components/VoteButton.svelte';
	import { userName } from '$lib/stores/votes';

	onMount(async () => {
		await fetchReportDates();
		if ($selectedDate) {
			await fetchReport($selectedDate);
		}
		await fetchTeamVotes();
	});

	async function handleDateChange(event: Event) {
		const target = event.target as HTMLSelectElement;
		const date = target.value;
		selectedDate.set(date);
		await fetchReport(date);
	}

	// Team view helpers
	const teamFilters: { key: VoteFilter; label: string }[] = [
		{ key: 'all', label: '전체' },
		{ key: 'applicable', label: '🔧 적용' },
		{ key: 'idea', label: '💡 아이디어' },
		{ key: 'pass', label: '⏭️ 패스' }
	];

	const voteCardBorder: Record<string, string> = {
		applicable: 'border-l-blue-500',
		idea: 'border-l-amber-400',
		pass: 'border-l-gray-400'
	};

	function skimUserVote(sp: SkimPaper): 'applicable' | 'idea' | 'pass' | null {
		const webUserId = `web_${$userName}`;
		if (sp.applicable_voters?.some((v) => v.user_id === webUserId)) return 'applicable';
		if (sp.idea_voters?.some((v) => v.user_id === webUserId)) return 'idea';
		if (sp.pass_voters?.some((v) => v.user_id === webUserId)) return 'pass';
		return null;
	}
</script>

<svelte:head>
	<title>Paper Digest Dashboard</title>
</svelte:head>

<div>
	<!-- ================================================================ -->
	<!-- DATE VIEW: 데일리 논문                                            -->
	<!-- ================================================================ -->
	{#if $viewMode === 'date'}

		<!-- Date Selector + Stats -->
		<div class="bg-white rounded-xl shadow-sm border border-gray-200 p-4 mb-6">
			<div class="flex flex-wrap items-center gap-4">
				<!-- Date Selector -->
				{#if $reportDates.length > 0}
					<div class="flex items-center gap-2">
						<label for="date-select" class="text-sm font-medium text-gray-600">📅 날짜</label>
						<select
							id="date-select"
							class="px-3 py-1.5 bg-white border border-gray-300 rounded-lg shadow-sm text-sm font-medium cursor-pointer
									 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
							value={$selectedDate}
							on:change={handleDateChange}
						>
							{#each $reportDates as date}
								<option value={date}>{date}</option>
							{/each}
						</select>
					</div>
				{/if}

				<!-- Stats (inline) -->
				{#if $reportData}
					<div class="flex items-center gap-3 text-xs text-gray-500 ml-auto">
						<span class="text-blue-700 font-medium">🔧 {$stats.applicable}</span>
						<span class="text-amber-700 font-medium">💡 {$stats.idea}</span>
						<span class="text-gray-600 font-medium">⏭️ {$stats.pass}</span>
						<span class="text-gray-400">미투표 {$stats.noVote}</span>
						<span class="text-gray-400">총 {$stats.total}편</span>
					</div>
				{/if}
			</div>
		</div>

		<!-- Loading -->
		{#if $isLoading}
			<div class="flex items-center justify-center py-12">
				<div class="flex items-center gap-3 text-gray-500">
					<svg class="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
						<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
						<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
					</svg>
					<span>로딩 중...</span>
				</div>
			</div>
		{/if}

		<!-- Error -->
		{#if $error}
			<div class="bg-red-50 border border-red-200 rounded-xl p-4 mb-6">
				<div class="flex items-center gap-2 text-red-700">
					<span>⚠️</span><span>{$error}</span>
				</div>
			</div>
		{/if}

		<!-- Empty -->
		{#if !$isLoading && $reportDates.length === 0}
			<div class="text-center py-12">
				<div class="text-6xl mb-4">📭</div>
				<h3 class="text-lg font-medium text-gray-700 mb-2">리포트가 없습니다</h3>
				<p class="text-gray-500">아직 생성된 리포트가 없습니다.</p>
			</div>
		{/if}

		<!-- Deep Analysis Papers -->
		{#if $reportData && $reportData.papers.length > 0}
			<div class="space-y-4">
				{#each $reportData.papers as paper (paper.arxiv_id)}
					<PaperCard {paper} />
				{/each}
			</div>
		{:else if $reportData && $reportData.papers.length === 0 && (!$reportData.skim_papers || $reportData.skim_papers.length === 0)}
			<div class="text-center py-12">
				<div class="text-6xl mb-4">📄</div>
				<h3 class="text-lg font-medium text-gray-700 mb-2">논문이 없습니다</h3>
				<p class="text-gray-500">이 날짜에는 논문이 없습니다.</p>
			</div>
		{/if}

		<!-- Skim Papers Section -->
		{#if $reportData && $reportData.skim_papers && $reportData.skim_papers.length > 0}
			<div class="mt-8">
				<h3 class="text-base font-semibold text-gray-700 mb-3 flex items-center gap-2">
					📋 기타 주목할 논문
					<span class="text-xs font-normal text-gray-400">{$reportData.skim_papers.length}편</span>
				</h3>
				<div class="space-y-2">
					{#each $reportData.skim_papers as sp (sp.arxiv_id)}
						<div class="bg-white rounded-lg shadow-sm border border-gray-200 p-3">
							<div class="flex items-start justify-between gap-3">
								<div class="flex-1 min-w-0">
									<a
										href="https://arxiv.org/abs/{sp.arxiv_id}"
										target="_blank"
										rel="noopener noreferrer"
										class="text-sm font-medium text-gray-900 hover:text-indigo-600 line-clamp-1"
									>
										{sp.title}
									</a>
									<p class="text-xs text-gray-500 mt-0.5 line-clamp-1">{sp.one_liner}</p>
									<div class="flex items-center gap-2 mt-1">
										{#if sp.category}
											<span class="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">{sp.category}</span>
										{/if}
										{#each sp.matched_keywords.slice(0, 3) as kw}
											<span class="text-[10px] px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-600">{kw}</span>
										{/each}
									</div>
								</div>
								<div class="shrink-0">
									<VoteButton
										arxivId={sp.arxiv_id}
										applicableCount={sp.applicable_count}
										ideaCount={sp.idea_count}
										passCount={sp.pass_count}
										currentUserVote={skimUserVote(sp)}
										compact={true}
									/>
								</div>
							</div>
						</div>
					{/each}
				</div>
			</div>
		{/if}

	<!-- ================================================================ -->
	<!-- TEAM VIEW: 팀 결정                                                -->
	<!-- ================================================================ -->
	{:else}

		<!-- Filter Tabs + Date -->
		<div class="bg-white rounded-xl shadow-sm border border-gray-200 p-4 mb-6">
			<div class="flex items-center gap-3 flex-wrap">
				{#each teamFilters as f}
					<button
						class="px-3 py-1.5 text-sm font-medium rounded-lg transition-colors
								 {$teamVoteFilter === f.key
									? 'bg-indigo-100 text-indigo-700'
									: 'text-gray-500 hover:bg-gray-100'}"
						on:click={() => teamVoteFilter.set(f.key)}
					>
						{f.label}
					</button>
				{/each}

				<div class="flex items-center gap-2 ml-auto">
					<select
						class="px-2.5 py-1.5 bg-white border border-gray-300 rounded-lg shadow-sm text-xs font-medium cursor-pointer
								 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
						value={$teamDateFilter}
						on:change={(e) => teamDateFilter.set(e.currentTarget.value)}
					>
						<option value="all">전체 날짜</option>
						{#each $teamDates as d}
							<option value={d}>{d}</option>
						{/each}
					</select>
					<span class="text-xs text-gray-400">{$filteredTeamVotes.length}편</span>
				</div>
			</div>
		</div>

		{#if $teamVoteLoading}
			<div class="flex items-center justify-center py-12">
				<div class="flex items-center gap-3 text-gray-500">
					<svg class="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
						<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
						<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
					</svg>
					<span>로딩 중...</span>
				</div>
			</div>
		{:else if $filteredTeamVotes.length === 0}
			<div class="text-center py-12">
				<div class="text-6xl mb-4">🗳️</div>
				<h3 class="text-lg font-medium text-gray-700 mb-2">투표된 논문이 없습니다</h3>
				<p class="text-gray-500">아직 투표가 진행되지 않았습니다.</p>
			</div>
		{:else}
			<div class="space-y-2">
				{#each $filteredTeamVotes as paper (paper.arxiv_id + paper.date)}
					<a
						href="/paper/{paper.arxiv_id}"
						class="block bg-white rounded-lg shadow-sm border-l-4 border border-gray-200 {voteCardBorder[paper.dominant_vote] ?? ''}
								 p-4 hover:shadow-md transition-shadow"
					>
						<div class="flex items-start justify-between gap-4">
							<div class="flex-1 min-w-0">
								<h3 class="text-sm font-semibold text-gray-900 line-clamp-2">{paper.title}</h3>
								<div class="flex items-center gap-3 mt-1.5 text-xs text-gray-500">
									<span class="font-mono">{paper.date}</span>
									<span>arXiv: {paper.arxiv_id}</span>
								</div>
							</div>
							<div class="shrink-0 flex items-center gap-1.5 text-xs">
								{#if paper.applicable_count > 0}
									<span class="px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 font-medium">🔧 {paper.applicable_count}</span>
								{/if}
								{#if paper.idea_count > 0}
									<span class="px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 font-medium">💡 {paper.idea_count}</span>
								{/if}
								{#if paper.pass_count > 0}
									<span class="px-1.5 py-0.5 rounded bg-gray-100 text-gray-600 font-medium">⏭️ {paper.pass_count}</span>
								{/if}
							</div>
						</div>
					</a>
				{/each}
			</div>
		{/if}
	{/if}
</div>
