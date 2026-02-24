<script lang="ts">
	import { onMount } from 'svelte';
	import {
		userName,
		selectedDate,
		fetchComments,
		submitComment,
		deleteComment
	} from '$lib/stores/votes';
	import type { Comment } from '$lib/stores/votes';

	export let arxivId: string;
	export let date: string = '';

	let comments: Comment[] = [];
	let newCommentText = '';
	let isSubmitting = false;
	let isLoadingComments = false;

	$: effectiveDate = date || $selectedDate;

	onMount(async () => {
		if (effectiveDate && arxivId) {
			await loadComments();
		}
	});

	async function loadComments() {
		isLoadingComments = true;
		comments = await fetchComments(effectiveDate, arxivId);
		isLoadingComments = false;
	}

	async function handleSubmit() {
		if (!$userName) {
			alert('먼저 닉네임을 입력해주세요!');
			return;
		}
		if (!newCommentText.trim()) return;

		isSubmitting = true;
		const comment = await submitComment(arxivId, effectiveDate, $userName, newCommentText.trim());
		if (comment) {
			comments = [...comments, comment];
			newCommentText = '';
		}
		isSubmitting = false;
	}

	async function handleDelete(commentId: string) {
		if (!confirm('댓글을 삭제하시겠습니까?')) return;

		const success = await deleteComment(effectiveDate, arxivId, commentId, $userName);
		if (success) {
			comments = comments.filter((c) => c.id !== commentId);
		}
	}

	function formatTime(isoString: string): string {
		const date = new Date(isoString);
		return date.toLocaleString('ko-KR', {
			month: 'short',
			day: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		});
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			handleSubmit();
		}
	}
</script>

<div class="mt-4">
	<h4 class="text-sm font-semibold text-gray-700 mb-3">💬 댓글 ({comments.length})</h4>

	<!-- Comment List -->
	{#if isLoadingComments}
		<div class="text-sm text-gray-400 py-2">댓글 로딩 중...</div>
	{:else if comments.length > 0}
		<div class="space-y-2 mb-3">
			{#each comments as comment (comment.id)}
				<div class="flex items-start gap-2 bg-gray-50 rounded-lg p-3 text-sm">
					<div class="flex-1">
						<div class="flex items-center gap-2 mb-1">
							<span class="font-medium text-gray-800">{comment.user_name}</span>
							<span class="text-xs text-gray-400">{formatTime(comment.created_at)}</span>
						</div>
						<p class="text-gray-700 whitespace-pre-wrap">{comment.text}</p>
					</div>
					{#if comment.user_name === $userName}
						<button
							class="text-gray-400 hover:text-red-500 transition-colors text-xs shrink-0"
							on:click={() => handleDelete(comment.id)}
							title="삭제"
						>
							✕
						</button>
					{/if}
				</div>
			{/each}
		</div>
	{:else}
		<p class="text-sm text-gray-400 italic mb-3">아직 댓글이 없습니다</p>
	{/if}

	<!-- Comment Input -->
	<div class="flex gap-2">
		<input
			type="text"
			class="flex-1 text-sm border border-gray-300 rounded-lg px-3 py-2
					 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
			placeholder={$userName ? '댓글을 입력하세요...' : '먼저 닉네임을 설정해주세요'}
			bind:value={newCommentText}
			on:keydown={handleKeydown}
			disabled={!$userName || isSubmitting}
		/>
		<button
			class="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg
					 hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
			on:click={handleSubmit}
			disabled={!$userName || !newCommentText.trim() || isSubmitting}
		>
			{isSubmitting ? '...' : '작성'}
		</button>
	</div>
</div>
