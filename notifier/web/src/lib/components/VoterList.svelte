<script lang="ts">
	import type { Voter } from '$lib/stores/votes';

	export let applicableVoters: Voter[] = [];
	export let ideaVoters: Voter[] = [];
	export let passVoters: Voter[] = [];

	function formatTime(isoString: string): string {
		const date = new Date(isoString);
		return date.toLocaleString('ko-KR', {
			month: 'short',
			day: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		});
	}

	function getInitial(name: string): string {
		return name.charAt(0).toUpperCase();
	}
</script>

<div class="flex flex-wrap gap-4 text-sm">
	{#if applicableVoters.length > 0}
		<div class="flex items-center gap-1.5">
			<span class="text-blue-600 font-medium">🔧</span>
			<div class="flex -space-x-1">
				{#each applicableVoters as voter}
					<span
						class="inline-flex items-center justify-center w-6 h-6 bg-blue-100 text-blue-700
								 text-xs font-medium rounded-full border-2 border-white cursor-default"
						title="{voter.user_name} - {formatTime(voter.voted_at)}"
					>
						{getInitial(voter.user_name)}
					</span>
				{/each}
			</div>
			<span class="text-gray-600 ml-1">
				{applicableVoters.map((v) => v.user_name).join(', ')}
			</span>
		</div>
	{/if}

	{#if ideaVoters.length > 0}
		<div class="flex items-center gap-1.5">
			<span class="text-amber-600 font-medium">💡</span>
			<div class="flex -space-x-1">
				{#each ideaVoters as voter}
					<span
						class="inline-flex items-center justify-center w-6 h-6 bg-amber-100 text-amber-700
								 text-xs font-medium rounded-full border-2 border-white cursor-default"
						title="{voter.user_name} - {formatTime(voter.voted_at)}"
					>
						{getInitial(voter.user_name)}
					</span>
				{/each}
			</div>
			<span class="text-gray-600 ml-1">
				{ideaVoters.map((v) => v.user_name).join(', ')}
			</span>
		</div>
	{/if}

	{#if passVoters.length > 0}
		<div class="flex items-center gap-1.5">
			<span class="text-gray-500 font-medium">⏭️</span>
			<div class="flex -space-x-1">
				{#each passVoters as voter}
					<span
						class="inline-flex items-center justify-center w-6 h-6 bg-gray-100 text-gray-600
								 text-xs font-medium rounded-full border-2 border-white cursor-default"
						title="{voter.user_name} - {formatTime(voter.voted_at)}"
					>
						{getInitial(voter.user_name)}
					</span>
				{/each}
			</div>
			<span class="text-gray-600 ml-1">
				{passVoters.map((v) => v.user_name).join(', ')}
			</span>
		</div>
	{/if}

	{#if applicableVoters.length === 0 && ideaVoters.length === 0 && passVoters.length === 0}
		<span class="text-gray-400 italic">아직 투표가 없습니다</span>
	{/if}
</div>
