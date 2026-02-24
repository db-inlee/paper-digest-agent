<script lang="ts">
	import { reportDates, selectedDate, fetchReport } from '$lib/stores/votes';

	async function handleChange(event: Event) {
		const target = event.target as HTMLSelectElement;
		const date = target.value;
		selectedDate.set(date);
		await fetchReport(date);
	}
</script>

<div class="flex items-center gap-2">
	<label for="date-select" class="text-sm font-medium text-gray-600">날짜:</label>
	<select
		id="date-select"
		class="px-3 py-2 bg-white border border-gray-300 rounded-lg shadow-sm
				 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500
				 text-sm font-medium cursor-pointer"
		value={$selectedDate}
		on:change={handleChange}
	>
		{#each $reportDates as date}
			<option value={date}>{date}</option>
		{/each}
	</select>
</div>
