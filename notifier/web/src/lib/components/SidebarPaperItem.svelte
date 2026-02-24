<script lang="ts">
	import type { TeamVotePaper } from '$lib/stores/teamVotes';

	export let paper: TeamVotePaper;

	const voteColors: Record<string, string> = {
		applicable: 'border-l-blue-500',
		idea: 'border-l-amber-400',
		pass: 'border-l-gray-400'
	};

	const voteEmoji: Record<string, string> = {
		applicable: '🔧',
		idea: '💡',
		pass: '⏭️'
	};
</script>

<a
	href="/paper/{paper.arxiv_id}"
	class="block px-3 py-2 border-l-3 {voteColors[paper.dominant_vote] ?? 'border-l-gray-200'}
			 hover:bg-gray-50 transition-colors cursor-pointer"
>
	<div class="text-xs font-medium text-gray-800 line-clamp-2 leading-tight">
		{paper.title}
	</div>
	<div class="flex items-center gap-2 mt-1 text-[10px] text-gray-500">
		<span>{paper.date}</span>
		<span>{voteEmoji[paper.dominant_vote] ?? ''} {paper.applicable_count + paper.idea_count + paper.pass_count}</span>
	</div>
</a>
