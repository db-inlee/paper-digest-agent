<script lang="ts">
	import { pipelineStatus, triggerPipeline, fetchPipelineStatus } from '$lib/stores/pipeline';
	import { fetchReportDates } from '$lib/stores/votes';
	import { onMount } from 'svelte';

	let triggering = false;

	onMount(() => {
		fetchPipelineStatus();
	});

	async function handleRun() {
		triggering = true;
		const ok = await triggerPipeline();
		triggering = false;
		if (!ok && $pipelineStatus.state === 'running') {
			alert('파이프라인이 이미 실행 중입니다.');
		}
	}

	$: if ($pipelineStatus.state === 'completed') {
		fetchReportDates();
	}
</script>

<div class="flex items-center gap-2">
	{#if $pipelineStatus.state === 'running'}
		<div class="flex items-center gap-1.5 text-xs text-amber-700 bg-amber-50 px-2.5 py-1 rounded-full">
			<svg class="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24" fill="none">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
			<span>실행 중…</span>
		</div>
	{:else if $pipelineStatus.state === 'completed'}
		<span class="text-xs text-green-700 bg-green-50 px-2.5 py-1 rounded-full">완료</span>
	{:else if $pipelineStatus.state === 'error'}
		<span class="text-xs text-red-700 bg-red-50 px-2.5 py-1 rounded-full" title={$pipelineStatus.error || ''}>오류</span>
	{/if}

	<button
		class="flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-lg
				 bg-indigo-600 text-white hover:bg-indigo-700 transition-colors
				 disabled:opacity-50 disabled:cursor-not-allowed"
		disabled={triggering || $pipelineStatus.state === 'running'}
		on:click={handleRun}
	>
		<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
			<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
		</svg>
		파이프라인 실행
	</button>
</div>
