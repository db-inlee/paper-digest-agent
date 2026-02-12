<script lang="ts">
	import { onDestroy } from 'svelte';

	const API_BASE = '/api';

	interface AddJob {
		state: 'running' | 'completed' | 'error';
		arxiv_id: string;
		title: string;
		date: string;
		error: string | null;
	}

	let url = '';
	let submitting = false;
	let submitError = '';
	let jobs: AddJob[] = [];
	let pollInterval: ReturnType<typeof setInterval> | null = null;

	async function fetchJobs() {
		try {
			const res = await fetch(`${API_BASE}/papers/add/status`);
			if (res.ok) {
				const data = await res.json();
				jobs = data.jobs;
				// Stop polling if no running jobs
				if (!jobs.some((j) => j.state === 'running') && pollInterval) {
					clearInterval(pollInterval);
					pollInterval = null;
				}
			}
		} catch {
			// ignore
		}
	}

	function startPolling() {
		if (pollInterval) return;
		pollInterval = setInterval(fetchJobs, 3000);
	}

	async function handleSubmit() {
		if (!url.trim()) return;
		submitting = true;
		submitError = '';

		try {
			const res = await fetch(`${API_BASE}/papers/add`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ url: url.trim() })
			});

			if (!res.ok) {
				const data = await res.json();
				throw new Error(data.detail || 'Failed to submit paper');
			}

			const data = await res.json();
			// Add to local jobs list immediately
			jobs = [
				{
					state: 'running',
					arxiv_id: data.arxiv_id,
					title: data.title,
					date: data.date,
					error: null
				},
				...jobs.filter((j) => j.arxiv_id !== data.arxiv_id)
			];
			url = '';
			startPolling();
		} catch (e) {
			submitError = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			submitting = false;
		}
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Enter' && !submitting) {
			handleSubmit();
		}
	}

	// Fetch existing jobs on mount
	fetchJobs().then(() => {
		if (jobs.some((j) => j.state === 'running')) {
			startPolling();
		}
	});

	onDestroy(() => {
		if (pollInterval) clearInterval(pollInterval);
	});
</script>

<div class="max-w-2xl mx-auto">
	<h1 class="text-2xl font-bold text-gray-900 mb-2">논문 추가</h1>
	<p class="text-gray-600 mb-6">
		arXiv URL을 입력하면 기존 파이프라인과 동일하게 분석합니다.
	</p>

	<!-- Input Form -->
	<div class="bg-white rounded-xl border border-gray-200 p-5 mb-6">
		<label for="arxiv-url" class="block text-sm font-medium text-gray-700 mb-2">
			arXiv URL 또는 ID
		</label>
		<div class="flex gap-3">
			<input
				id="arxiv-url"
				type="text"
				bind:value={url}
				on:keydown={handleKeydown}
				placeholder="https://arxiv.org/abs/2602.06540 또는 2602.06540"
				disabled={submitting}
				class="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg
						 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500
						 disabled:bg-gray-50 disabled:text-gray-400
						 text-sm"
			/>
			<button
				on:click={handleSubmit}
				disabled={submitting || !url.trim()}
				class="px-5 py-2.5 bg-indigo-600 text-white rounded-lg text-sm font-medium
						 hover:bg-indigo-700 transition-colors
						 disabled:bg-gray-300 disabled:cursor-not-allowed
						 flex items-center gap-2"
			>
				{#if submitting}
					<span class="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
					분석 요청 중...
				{:else}
					🔬 분석 시작
				{/if}
			</button>
		</div>

		{#if submitError}
			<p class="mt-2 text-sm text-red-600">{submitError}</p>
		{/if}
	</div>

	<!-- Jobs List -->
	{#if jobs.length > 0}
		<h2 class="text-lg font-semibold text-gray-900 mb-3">분석 현황</h2>
		<div class="space-y-3">
			{#each jobs as job (job.arxiv_id)}
				<div
					class="bg-white rounded-xl border p-4 flex items-start gap-3
							 {job.state === 'running'
						? 'border-blue-200'
						: job.state === 'completed'
							? 'border-green-200'
							: 'border-red-200'}"
				>
					<!-- Status Icon -->
					<div class="shrink-0 mt-0.5">
						{#if job.state === 'running'}
							<span
								class="inline-block w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"
							/>
						{:else if job.state === 'completed'}
							<span class="text-green-500 text-lg">✅</span>
						{:else}
							<span class="text-red-500 text-lg">❌</span>
						{/if}
					</div>

					<!-- Content -->
					<div class="flex-1 min-w-0">
						<div class="flex items-center gap-2 mb-1">
							<span class="text-sm font-medium text-gray-900 truncate">{job.title}</span>
						</div>
						<div class="flex items-center gap-3 text-xs text-gray-500">
							<span>arXiv: {job.arxiv_id}</span>
							<span>{job.date}</span>
							{#if job.state === 'running'}
								<span class="text-blue-600 font-medium">분석 중...</span>
							{:else if job.state === 'completed'}
								<a
									href="/"
									class="text-green-600 font-medium hover:underline"
								>
									논문 보기 →
								</a>
							{:else}
								<span class="text-red-600">{job.error || '분석 실패'}</span>
							{/if}
						</div>
					</div>
				</div>
			{/each}
		</div>
	{:else}
		<div class="text-center py-12 text-gray-400">
			<p class="text-4xl mb-3">📄</p>
			<p class="text-sm">아직 추가한 논문이 없습니다.</p>
			<p class="text-sm">위에서 arXiv URL을 입력하여 논문을 분석해보세요.</p>
		</div>
	{/if}
</div>
