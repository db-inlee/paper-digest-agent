<script lang="ts">
	import { reportDates, selectedDate, fetchReport, viewMode } from '$lib/stores/votes';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';

	async function selectDate(date: string) {
		viewMode.set('date');
		selectedDate.set(date);
		await fetchReport(date);
		if ($page.url.pathname !== '/') {
			goto('/');
		}
	}
</script>

<div class="mb-4">
	<div class="px-3 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">
		📅 데일리 논문
	</div>
	<div class="space-y-0.5">
		{#each $reportDates as date}
			<button
				class="w-full text-left px-3 py-2 text-sm transition-colors rounded-md
						 {$viewMode === 'date' && $selectedDate === date
							? 'bg-indigo-50 text-indigo-700 font-medium'
							: 'text-gray-700 hover:bg-gray-50'}"
				on:click={() => selectDate(date)}
			>
				{date}
			</button>
		{/each}

		{#if $reportDates.length === 0}
			<div class="px-3 py-2 text-xs text-gray-400">날짜 없음</div>
		{/if}
	</div>
</div>
