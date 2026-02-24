<script lang="ts">
	import { viewMode } from '$lib/stores/votes';
	import type { ViewMode } from '$lib/stores/votes';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';

	const tabs: { key: ViewMode; label: string; emoji: string }[] = [
		{ key: 'date', label: '데일리 논문', emoji: '📅' },
		{ key: 'team', label: '팀 결정', emoji: '🗳️' }
	];

	function selectTab(key: ViewMode) {
		viewMode.set(key);
		if ($page.url.pathname !== '/') {
			goto('/');
		}
	}
</script>

<aside class="w-[200px] shrink-0 bg-gray-50 border-r border-gray-200 flex flex-col pt-3">
	<nav class="flex flex-col gap-1 px-3">
		{#each tabs as tab}
			<button
				class="w-full text-left px-3 py-2.5 text-sm font-medium rounded-lg transition-colors
						 {$viewMode === tab.key
							? 'bg-indigo-50 text-indigo-700'
							: 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'}"
				on:click={() => selectTab(tab.key)}
			>
				<span class="mr-2">{tab.emoji}</span>{tab.label}
			</button>
		{/each}
	</nav>
</aside>
