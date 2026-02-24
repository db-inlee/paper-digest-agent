<script lang="ts">
	import type { Paper } from '$lib/stores/votes';
	import { userName } from '$lib/stores/votes';
	import VoteButton from './VoteButton.svelte';
	import VoterList from './VoterList.svelte';

	export let paper: Paper;

	$: totalVotes = paper.applicable_count + paper.idea_count + paper.pass_count;
	$: applicablePercent = totalVotes > 0 ? (paper.applicable_count / totalVotes) * 100 : 0;
	$: ideaPercent = totalVotes > 0 ? (paper.idea_count / totalVotes) * 100 : 0;
	$: passPercent = totalVotes > 0 ? (paper.pass_count / totalVotes) * 100 : 0;

	// Check if current user has voted
	$: currentUserVote = ((): 'applicable' | 'idea' | 'pass' | null => {
		const webUserId = `web_${$userName}`;
		if (paper.applicable_voters.some((v) => v.user_id === webUserId)) return 'applicable';
		if (paper.idea_voters.some((v) => v.user_id === webUserId)) return 'idea';
		if (paper.pass_voters.some((v) => v.user_id === webUserId)) return 'pass';
		return null;
	})();

	// Determine status color based on dominant vote
	$: statusClass =
		paper.applicable_count > 0 && paper.applicable_count >= paper.idea_count && paper.applicable_count >= paper.pass_count
			? 'border-l-blue-500'
			: paper.idea_count > 0 && paper.idea_count >= paper.applicable_count && paper.idea_count >= paper.pass_count
				? 'border-l-amber-500'
				: paper.pass_count > 0
					? 'border-l-gray-400'
					: 'border-l-gray-300';
</script>

<article
	class="bg-white rounded-xl shadow-sm border border-gray-200 border-l-4 {statusClass}
			 overflow-hidden transition-shadow hover:shadow-md"
>
	<div class="p-5">
		<!-- Header: Title and Stars -->
		<div class="flex items-start justify-between gap-4 mb-3">
			<h3 class="text-lg font-semibold text-gray-900 leading-tight flex-1">
				<span class="mr-2 text-yellow-500">{paper.star_emoji}</span>
				<a
					href="/paper/{paper.arxiv_id}"
					class="hover:text-indigo-600 transition-colors"
				>
					{paper.title}
				</a>
			</h3>
			<span class="text-sm text-gray-500 whitespace-nowrap">
				{paper.score}/{paper.max_score}
			</span>
		</div>

		<!-- arXiv ID -->
		<div class="text-sm text-gray-500 mb-3">
			arXiv: {paper.arxiv_id}
		</div>

		<!-- Summary -->
		<p class="text-gray-700 mb-4 leading-relaxed">
			📝 {paper.summary}
		</p>

		<!-- Vote Progress Bar (3-segment) -->
		{#if totalVotes > 0}
			<div class="mb-4">
				<div class="flex items-center gap-0 mb-1.5">
					<div class="flex-1 h-3 bg-gray-200 rounded-full overflow-hidden flex">
						{#if applicablePercent > 0}
							<div
								class="h-full bg-blue-500 transition-all duration-300"
								style="width: {applicablePercent}%"
							/>
						{/if}
						{#if ideaPercent > 0}
							<div
								class="h-full bg-amber-400 transition-all duration-300"
								style="width: {ideaPercent}%"
							/>
						{/if}
						{#if passPercent > 0}
							<div
								class="h-full bg-gray-400 transition-all duration-300"
								style="width: {passPercent}%"
							/>
						{/if}
					</div>
				</div>
				<div class="flex justify-between text-xs text-gray-500">
					<span class="text-blue-600">🔧 {paper.applicable_count}</span>
					<span class="text-amber-600">💡 {paper.idea_count}</span>
					<span class="text-gray-500">⏭️ {paper.pass_count}</span>
				</div>
			</div>
		{/if}

		<!-- Voter List -->
		<div class="mb-4">
			<VoterList
				applicableVoters={paper.applicable_voters}
				ideaVoters={paper.idea_voters}
				passVoters={paper.pass_voters}
			/>
		</div>

		<!-- Actions -->
		<div class="flex items-center justify-between gap-4 pt-3 border-t border-gray-100">
			<VoteButton
				arxivId={paper.arxiv_id}
				applicableCount={paper.applicable_count}
				ideaCount={paper.idea_count}
				passCount={paper.pass_count}
				{currentUserVote}
			/>

			<div class="flex items-center gap-2">
				<a
					href="/paper/{paper.arxiv_id}"
					class="flex items-center gap-1.5 px-3 py-2 text-sm text-white
							 bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors"
				>
					상세 보기
				</a>
				{#if paper.github_url}
					<a
						href={paper.github_url}
						target="_blank"
						rel="noopener noreferrer"
						class="flex items-center gap-1.5 px-3 py-2 text-sm text-gray-600
								 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
					>
						<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
							<path
								d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"
							/>
						</svg>
						GitHub
					</a>
				{/if}
				<a
					href={paper.arxiv_url}
					target="_blank"
					rel="noopener noreferrer"
					class="flex items-center gap-1.5 px-3 py-2 text-sm text-indigo-600
							 bg-indigo-50 rounded-lg hover:bg-indigo-100 transition-colors"
				>
					📄 arXiv
				</a>
			</div>
		</div>
	</div>
</article>
