<script lang="ts">
	import type { Verification } from '$lib/types/paperDetail';

	export let verification: Verification;

	const reliabilityConfig: Record<string, { label: string; color: string; bg: string }> = {
		high: { label: 'High', color: 'text-green-800', bg: 'bg-green-100 border-green-300' },
		medium: { label: 'Medium', color: 'text-yellow-800', bg: 'bg-yellow-100 border-yellow-300' },
		low: { label: 'Low', color: 'text-red-800', bg: 'bg-red-100 border-red-300' }
	};

	$: reliability = reliabilityConfig[verification.overall_reliability] ?? {
		label: verification.overall_reliability,
		color: 'text-gray-800',
		bg: 'bg-gray-100 border-gray-300'
	};

	function statusIcon(status: string): string {
		if (status === 'verified') return '✅';
		if (status === 'contradicted') return '❌';
		return '❓';
	}

	function statusBg(status: string): string {
		if (status === 'verified') return 'bg-green-50 border-green-200';
		if (status === 'contradicted') return 'bg-red-50 border-red-200';
		return 'bg-yellow-50 border-yellow-200';
	}
</script>

<section class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
	<div class="flex items-center justify-between mb-5">
		<h2 class="text-xl font-bold text-gray-900">검증 (Verification)</h2>
		<span class="px-3 py-1 text-sm font-semibold border rounded-full {reliability.bg} {reliability.color}">
			신뢰도: {reliability.label}
		</span>
	</div>

	<!-- Counts -->
	<div class="flex gap-4 mb-6">
		<div class="flex-1 text-center p-3 bg-green-50 rounded-lg">
			<p class="text-2xl font-bold text-green-700">{verification.verified_count}</p>
			<p class="text-xs text-green-600">검증됨</p>
		</div>
		<div class="flex-1 text-center p-3 bg-yellow-50 rounded-lg">
			<p class="text-2xl font-bold text-yellow-700">{verification.unverified_count}</p>
			<p class="text-xs text-yellow-600">미검증</p>
		</div>
		<div class="flex-1 text-center p-3 bg-red-50 rounded-lg">
			<p class="text-2xl font-bold text-red-700">{verification.contradicted_count}</p>
			<p class="text-xs text-red-600">모순</p>
		</div>
	</div>

	<!-- Results per claim -->
	{#if verification.results.length > 0}
		<div class="space-y-3 mb-6">
			{#each verification.results as r}
				<div class="border rounded-lg p-4 {statusBg(r.status)}">
					<div class="flex items-start gap-2 mb-1">
						<span class="text-base">{statusIcon(r.status)}</span>
						<div class="flex-1">
							<p class="text-sm font-medium text-gray-900">
								<span class="font-mono text-xs text-gray-500">[{r.claim_id}]</span>
								{r.claim_text}
							</p>
							<p class="text-xs text-gray-600 mt-1">{r.evidence_found}</p>
							{#if r.notes}
								<p class="text-xs text-gray-500 mt-1 italic">{r.notes}</p>
							{/if}
							{#if r.correction_hint}
								<p class="text-xs text-red-600 mt-1">Correction: {r.correction_hint}</p>
							{/if}
						</div>
						<span class="text-xs text-gray-500 shrink-0">conf: {r.confidence}</span>
					</div>
				</div>
			{/each}
		</div>
	{/if}

	<!-- Summary -->
	<div class="bg-gray-50 rounded-lg p-4 mb-4">
		<h3 class="text-sm font-semibold text-gray-800 mb-1">요약</h3>
		<p class="text-sm text-gray-700">{verification.summary}</p>
	</div>

	<!-- Corrections needed -->
	{#if verification.corrections_needed.length > 0}
		<div>
			<h3 class="text-sm font-semibold text-gray-800 mb-2">수정 필요 항목</h3>
			<div class="flex flex-wrap gap-2">
				{#each verification.corrections_needed as c}
					<span class="text-xs px-2 py-1 bg-red-100 text-red-700 rounded-full">{c}</span>
				{/each}
			</div>
		</div>
	{/if}
</section>
