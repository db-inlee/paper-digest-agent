<script lang="ts">
	import { onMount } from 'svelte';
	import {
		topicsData,
		topicsLoading,
		topicsError,
		fetchTopics,
		toggleDefaultKeyword,
		removeKeyword
	} from '$lib/stores/topics';
	import TopicChip from '$lib/components/TopicChip.svelte';
	import ManualInput from '$lib/components/ManualInput.svelte';
	import ArxivExtractor from '$lib/components/ArxivExtractor.svelte';
	import TextExtractor from '$lib/components/TextExtractor.svelte';

	onMount(() => {
		fetchTopics();
	});
</script>

<svelte:head>
	<title>Topic Management</title>
</svelte:head>

<div class="max-w-4xl mx-auto">
	<!-- Header -->
	<div class="flex items-center justify-between mb-6">
		<div>
			<h2 class="text-2xl font-bold text-gray-900 mb-1">토픽 관리</h2>
			<p class="text-gray-500">논문 탐색에 사용되는 키워드를 관리합니다</p>
		</div>
		{#if $topicsData}
			<div class="flex items-center gap-2 px-4 py-2 bg-indigo-50 rounded-lg">
				<span class="text-sm text-indigo-700 font-medium">
					유효 키워드: {$topicsData.effective_keywords.length}개
				</span>
			</div>
		{/if}
	</div>

	<!-- Loading -->
	{#if $topicsLoading}
		<div class="flex items-center justify-center py-12">
			<div class="flex items-center gap-3 text-gray-500">
				<svg
					class="animate-spin h-5 w-5"
					xmlns="http://www.w3.org/2000/svg"
					fill="none"
					viewBox="0 0 24 24"
				>
					<circle
						class="opacity-25"
						cx="12"
						cy="12"
						r="10"
						stroke="currentColor"
						stroke-width="4"
					/>
					<path
						class="opacity-75"
						fill="currentColor"
						d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
					/>
				</svg>
				<span>로딩 중...</span>
			</div>
		</div>
	{/if}

	<!-- Error -->
	{#if $topicsError}
		<div class="bg-red-50 border border-red-200 rounded-xl p-4 mb-6">
			<div class="flex items-center gap-2 text-red-700">
				<span>!</span>
				<span>{$topicsError}</span>
			</div>
		</div>
	{/if}

	{#if $topicsData}
		<!-- Input Sections -->
		<div class="space-y-4 mb-8">
			<!-- Manual Input -->
			<div class="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
				<h3 class="text-sm font-semibold text-gray-700 mb-3">수동 키워드 입력</h3>
				<ManualInput />
			</div>

			<!-- ArXiv Extractor -->
			<div class="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
				<h3 class="text-sm font-semibold text-gray-700 mb-3">arXiv 논문에서 추출</h3>
				<ArxivExtractor />
			</div>

			<!-- Text Extractor -->
			<div class="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
				<h3 class="text-sm font-semibold text-gray-700 mb-3">텍스트에서 추출</h3>
				<TextExtractor />
			</div>
		</div>

		<!-- Default Keywords -->
		<div class="bg-white rounded-xl shadow-sm border border-gray-200 p-5 mb-4">
			<h3 class="text-base font-semibold text-gray-900 mb-1">기본 키워드</h3>
			<p class="text-sm text-gray-500 mb-4">클릭하여 활성/비활성 전환</p>
			<div class="flex flex-wrap gap-2">
				{#each $topicsData.default_keywords as kw}
					<TopicChip
						keyword={kw}
						type="default"
						disabled={$topicsData.disabled_default_keywords
							.map((d) => d.toLowerCase())
							.includes(kw.toLowerCase())}
						onToggle={() => toggleDefaultKeyword(kw)}
					/>
				{/each}
			</div>
		</div>

		<!-- Custom Keywords -->
		<div class="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
			<h3 class="text-base font-semibold text-gray-900 mb-1">커스텀 키워드</h3>
			<p class="text-sm text-gray-500 mb-4">사용자가 추가한 키워드</p>
			{#if $topicsData.custom_keywords.length === 0}
				<p class="text-sm text-gray-400">아직 추가된 키워드가 없습니다.</p>
			{:else}
				<div class="flex flex-wrap gap-2">
					{#each $topicsData.custom_keywords as entry}
						<TopicChip
							keyword={entry.keyword}
							type="custom"
							source={entry.source}
							onRemove={() => removeKeyword(entry.keyword)}
						/>
					{/each}
				</div>
			{/if}
		</div>
	{/if}
</div>
