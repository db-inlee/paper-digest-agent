<script lang="ts">
	import { addKeywords } from '$lib/stores/topics';
	import { userName } from '$lib/stores/votes';

	let input = '';
	let adding = false;

	async function handleAdd() {
		const keywords = input
			.split(',')
			.map((k) => k.trim())
			.filter((k) => k.length > 0);
		if (keywords.length === 0) return;

		adding = true;
		const ok = await addKeywords(keywords, 'manual', $userName);
		if (ok) input = '';
		adding = false;
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Enter') handleAdd();
	}
</script>

<div class="flex gap-2">
	<input
		type="text"
		bind:value={input}
		on:keydown={handleKeydown}
		placeholder="키워드 입력 (쉼표로 구분)"
		class="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm
				 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
		disabled={adding}
	/>
	<button
		on:click={handleAdd}
		disabled={adding || !input.trim()}
		class="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg
				 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed
				 transition-colors"
	>
		{adding ? '추가 중...' : '추가'}
	</button>
</div>
