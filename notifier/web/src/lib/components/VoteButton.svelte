<script lang="ts">
	import { userName, slackUserId, selectedDate, submitVote } from '$lib/stores/votes';

	export let arxivId: string;
	export let applicableCount: number;
	export let ideaCount: number;
	export let passCount: number;
	export let currentUserVote: 'applicable' | 'idea' | 'pass' | null = null;
	export let compact: boolean = false;

	let isVoting = false;

	async function handleVote(vote: 'applicable' | 'idea' | 'pass') {
		if (!$userName) {
			alert('먼저 닉네임을 입력해주세요!');
			return;
		}

		isVoting = true;
		await submitVote(arxivId, vote, $userName, $selectedDate, $slackUserId || undefined);
		isVoting = false;
	}
</script>

<div class="flex items-center gap-{compact ? '1' : '2'}">
	<button
		class="flex items-center gap-1 rounded-lg font-medium transition-all
				 {compact ? 'px-2 py-1 text-xs' : 'px-3 py-2 text-sm'}
				 {currentUserVote === 'applicable'
			? 'bg-blue-600 text-white shadow-md'
			: 'bg-blue-100 text-blue-700 hover:bg-blue-200'}
				 disabled:opacity-50 disabled:cursor-not-allowed"
		on:click={() => handleVote('applicable')}
		disabled={isVoting}
	>
		<span>🔧</span>
		{#if !compact}<span>실무 적용</span>{/if}
		{#if applicableCount > 0}
			<span class="px-1 py-0.5 bg-white/30 rounded-full text-xs">{applicableCount}</span>
		{/if}
	</button>

	<button
		class="flex items-center gap-1 rounded-lg font-medium transition-all
				 {compact ? 'px-2 py-1 text-xs' : 'px-3 py-2 text-sm'}
				 {currentUserVote === 'idea'
			? 'bg-amber-500 text-white shadow-md'
			: 'bg-amber-100 text-amber-700 hover:bg-amber-200'}
				 disabled:opacity-50 disabled:cursor-not-allowed"
		on:click={() => handleVote('idea')}
		disabled={isVoting}
	>
		<span>💡</span>
		{#if !compact}<span>아이디어</span>{/if}
		{#if ideaCount > 0}
			<span class="px-1 py-0.5 bg-white/30 rounded-full text-xs">{ideaCount}</span>
		{/if}
	</button>

	<button
		class="flex items-center gap-1 rounded-lg font-medium transition-all
				 {compact ? 'px-2 py-1 text-xs' : 'px-3 py-2 text-sm'}
				 {currentUserVote === 'pass'
			? 'bg-gray-600 text-white shadow-md'
			: 'bg-gray-100 text-gray-600 hover:bg-gray-200'}
				 disabled:opacity-50 disabled:cursor-not-allowed"
		on:click={() => handleVote('pass')}
		disabled={isVoting}
	>
		<span>⏭️</span>
		{#if !compact}<span>패스</span>{/if}
		{#if passCount > 0}
			<span class="px-1 py-0.5 bg-white/30 rounded-full text-xs">{passCount}</span>
		{/if}
	</button>
</div>
