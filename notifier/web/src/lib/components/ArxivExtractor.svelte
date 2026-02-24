<script lang="ts">
	import { extractFromArxiv, addKeywords } from '$lib/stores/topics';
	import { userName } from '$lib/stores/votes';

	let arxivId = '';
	let extracting = false;
	let adding = false;
	let preview: { title: string; keywords: string[] } | null = null;
	let selected: Set<string> = new Set();

	async function handleExtract() {
		if (!arxivId.trim()) return;
		extracting = true;
		preview = null;
		selected = new Set();

		const result = await extractFromArxiv(arxivId.trim());
		if (result) {
			preview = result;
			selected = new Set();
		}
		extracting = false;
	}

	async function handleAdd() {
		if (selected.size === 0) return;
		adding = true;
		await addKeywords([...selected], 'arxiv', $userName, arxivId.trim());
		preview = null;
		arxivId = '';
		selected = new Set();
		adding = false;
	}

	function toggleKeyword(kw: string) {
		if (selected.has(kw)) {
			selected.delete(kw);
		} else {
			selected.add(kw);
		}
		selected = selected;
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Enter') handleExtract();
	}
</script>

<div class="space-y-3">
	<div class="flex gap-2">
		<input
			type="text"
			bind:value={arxivId}
			on:keydown={handleKeydown}
			placeholder="arXiv ID (예: 2601.21181)"
			class="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm
					 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
			disabled={extracting}
		/>
		<button
			on:click={handleExtract}
			disabled={extracting || !arxivId.trim()}
			class="px-4 py-2 bg-purple-600 text-white text-sm font-medium rounded-lg
					 hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed
					 transition-colors"
		>
			{extracting ? '추출 중...' : '추출'}
		</button>
	</div>

	{#if preview}
		<div class="bg-purple-50 border border-purple-200 rounded-lg p-4">
			<p class="text-sm font-medium text-purple-900 mb-2">{preview.title}</p>
			<div class="flex flex-wrap gap-2 mb-3">
				{#each preview.keywords as kw}
					<label
						class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm cursor-pointer
								 border transition-all
								 {selected.has(kw)
							? 'bg-purple-200 text-purple-900 border-purple-300'
							: 'bg-white text-gray-500 border-gray-300'}"
					>
						<input
							type="checkbox"
							checked={selected.has(kw)}
							on:change={() => toggleKeyword(kw)}
							class="sr-only"
						/>
						{kw}
					</label>
				{/each}
			</div>
			<button
				on:click={handleAdd}
				disabled={adding || selected.size === 0}
				class="px-4 py-2 bg-purple-600 text-white text-sm font-medium rounded-lg
						 hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed
						 transition-colors"
			>
				{adding ? '추가 중...' : `선택 추가 (${selected.size}개)`}
			</button>
		</div>
	{/if}
</div>
