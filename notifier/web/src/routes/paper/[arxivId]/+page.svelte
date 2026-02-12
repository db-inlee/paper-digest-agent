<script lang="ts">
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import {
		paperDetail,
		isDetailLoading,
		fetchPaperDetail,
		reportData,
		selectedDate,
		error
	} from '$lib/stores/votes';
	import type { Paper } from '$lib/stores/votes';
	import ScoringSection from '$lib/components/detail/ScoringSection.svelte';
	import DeltaSection from '$lib/components/detail/DeltaSection.svelte';
	import ExtractionSection from '$lib/components/detail/ExtractionSection.svelte';
	import VerificationSection from '$lib/components/detail/VerificationSection.svelte';
	import VoteButton from '$lib/components/VoteButton.svelte';
	import CommentSection from '$lib/components/CommentSection.svelte';
	import { userName } from '$lib/stores/votes';

	$: arxivId = $page.params.arxivId;

	// Find paper in current report data for vote display
	let matchedPaper: Paper | null = null;
	$: if ($reportData) {
		matchedPaper = $reportData.papers.find((p) => p.arxiv_id === arxivId) ?? null;
	}

	$: currentUserVote = ((): 'applicable' | 'idea' | 'pass' | null => {
		if (!matchedPaper) return null;
		const webUserId = `web_${$userName}`;
		if (matchedPaper.applicable_voters.some((v) => v.user_id === webUserId)) return 'applicable';
		if (matchedPaper.idea_voters.some((v) => v.user_id === webUserId)) return 'idea';
		if (matchedPaper.pass_voters.some((v) => v.user_id === webUserId)) return 'pass';
		return null;
	})();

	onMount(() => {
		if (arxivId) fetchPaperDetail(arxivId);
	});
</script>

<div>
	<!-- Back link -->
	<a
		href="/"
		class="inline-flex items-center gap-1 text-sm text-indigo-600 hover:text-indigo-800 mb-6"
	>
		<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
		</svg>
		목록으로 돌아가기
	</a>

	{#if $isDetailLoading}
		<div class="flex justify-center py-20">
			<div class="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-500"></div>
		</div>
	{:else if $error}
		<div class="bg-red-50 text-red-700 p-4 rounded-lg text-sm">{$error}</div>
	{:else if $paperDetail}
		<!-- Title header -->
		<div class="mb-8">
			<h1 class="text-2xl font-bold text-gray-900 mb-2">
				{$paperDetail.extraction?.title ?? `arXiv: ${arxivId}`}
			</h1>
			<div class="flex items-center gap-3 text-sm text-gray-500">
				<span>arXiv: {arxivId}</span>
				<a
					href="https://arxiv.org/abs/{arxivId}"
					target="_blank"
					rel="noopener noreferrer"
					class="text-indigo-600 hover:underline"
				>
					논문 보기
				</a>
			</div>

			<!-- Vote buttons if paper is in current report -->
			{#if matchedPaper}
				<div class="mt-4">
					<VoteButton
						arxivId={matchedPaper.arxiv_id}
						applicableCount={matchedPaper.applicable_count}
						ideaCount={matchedPaper.idea_count}
						passCount={matchedPaper.pass_count}
						{currentUserVote}
					/>
				</div>
			{/if}
		</div>

		<!-- Sections -->
		<div class="space-y-6">
			{#if $paperDetail.scoring}
				<ScoringSection scoring={$paperDetail.scoring} />
			{/if}

			{#if $paperDetail.delta}
				<DeltaSection delta={$paperDetail.delta} />
			{/if}

			{#if $paperDetail.extraction}
				<ExtractionSection extraction={$paperDetail.extraction} />
			{/if}

			{#if $paperDetail.verification}
				<VerificationSection verification={$paperDetail.verification} />
			{/if}
		</div>

		<!-- Comments Section -->
		<div class="mt-8 pt-6 border-t border-gray-200">
			<CommentSection {arxivId} date={$selectedDate} />
		</div>
	{:else}
		<div class="text-center py-20 text-gray-500">
			논문 상세 정보를 찾을 수 없습니다.
		</div>
	{/if}
</div>
