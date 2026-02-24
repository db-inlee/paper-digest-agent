<script lang="ts">
	import { extractFromText, addKeywords } from '$lib/stores/topics';
	import { userName } from '$lib/stores/votes';

	let text = '';
	let extracting = false;
	let adding = false;
	let preview: { keywords: string[] } | null = null;
	let selected: Set<string> = new Set();

	async function handleExtract() {
		if (!text.trim()) return;
		extracting = true;
		preview = null;
		selected = new Set();

		const result = await extractFromText(text.trim());
		if (result) {
			preview = result;
			selected = new Set();
		}
		extracting = false;
	}

	async function handleAdd() {
		if (selected.size === 0) return;
		adding = true;
		await addKeywords([...selected], 'freetext', $userName);
		preview = null;
		text = '';
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
</script>

<div class="space-y-3">
	<div class="flex flex-col gap-2">
		<textarea
			bind:value={text}
			placeholder="관심 분야에 대한 텍스트를 입력하세요..."
			rows="3"
			class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm
					 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-teal-500
					 resize-y"
			disabled={extracting}
		/>
		<button
			on:click={handleExtract}
			disabled={extracting || !text.trim()}
			class="self-end px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg
					 hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed
					 transition-colors"
		>
			{extracting ? '추출 중...' : '키워드 추출'}
		</button>
	</div>

	{#if preview}
		<div class="bg-teal-50 border border-teal-200 rounded-lg p-4">
			<p class="text-sm font-medium text-teal-900 mb-2">추출된 키워드</p>
			<div class="flex flex-wrap gap-2 mb-3">
				{#each preview.keywords as kw}
					<label
						class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm cursor-pointer
								 border transition-all
								 {selected.has(kw)
							? 'bg-teal-200 text-teal-900 border-teal-300'
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
				class="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg
						 hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed
						 transition-colors"
			>
				{adding ? '추가 중...' : `선택 추가 (${selected.size}개)`}
			</button>
		</div>
	{/if}
</div>
