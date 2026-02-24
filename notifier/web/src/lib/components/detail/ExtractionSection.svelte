<script lang="ts">
	import type { Extraction } from '$lib/types/paperDetail';

	export let extraction: Extraction;
</script>

<section class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
	<h2 class="text-xl font-bold text-gray-900 mb-5">추출 정보 (Extraction)</h2>

	<!-- Problem Definition -->
	<div class="mb-6">
		<h3 class="text-sm font-semibold text-gray-800 mb-2">문제 정의</h3>
		<p class="text-sm text-gray-700 leading-relaxed bg-gray-50 rounded-lg p-4">
			{extraction.problem_definition.statement}
		</p>
		{#if extraction.problem_definition.structural_limitation}
			<p class="text-sm text-orange-700 mt-2 bg-orange-50 rounded-lg p-3">
				<strong>구조적 한계:</strong> {extraction.problem_definition.structural_limitation}
			</p>
		{/if}
	</div>

	<!-- Baselines -->
	{#if extraction.baselines.length > 0}
		<div class="mb-6">
			<h3 class="text-sm font-semibold text-gray-800 mb-3">베이스라인</h3>
			<div class="grid grid-cols-1 md:grid-cols-2 gap-3">
				{#each extraction.baselines as b}
					<div class="border border-gray-200 rounded-lg p-4">
						<p class="font-semibold text-sm text-gray-900 mb-1">{b.name}</p>
						<p class="text-sm text-gray-600 mb-2">{b.description}</p>
						<p class="text-xs text-red-600"><strong>한계:</strong> {b.limitation}</p>
					</div>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Method Components -->
	{#if extraction.method_components.length > 0}
		<div class="mb-6">
			<h3 class="text-sm font-semibold text-gray-800 mb-3">방법론 컴포넌트</h3>
			<div class="space-y-3">
				{#each extraction.method_components as m}
					<div class="border border-indigo-200 bg-indigo-50 rounded-lg p-4">
						<p class="font-semibold text-sm text-indigo-900 mb-1">{m.name}</p>
						<p class="text-sm text-gray-700 mb-2">{m.description}</p>
						<div class="flex flex-wrap gap-4 text-xs text-gray-600">
							{#if m.inputs.length > 0}
								<span><strong>Inputs:</strong> {m.inputs.join(', ')}</span>
							{/if}
							{#if m.outputs.length > 0}
								<span><strong>Outputs:</strong> {m.outputs.join(', ')}</span>
							{/if}
						</div>
					</div>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Benchmark -->
	{#if extraction.benchmark}
		<div class="mb-6">
			<h3 class="text-sm font-semibold text-gray-800 mb-3">벤치마크</h3>
			<div class="bg-gray-50 rounded-lg p-4">
				<p class="text-sm text-gray-700 mb-2">
					<strong>Dataset:</strong> {extraction.benchmark.dataset} &nbsp;|&nbsp;
					<strong>Metrics:</strong> {extraction.benchmark.metrics.join(', ')}
				</p>

				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b border-gray-300">
								<th class="text-left py-2 pr-4 text-gray-700">Method</th>
								<th class="text-left py-2 text-gray-700">Result</th>
							</tr>
						</thead>
						<tbody>
							{#each Object.entries(extraction.benchmark.baseline_results) as [method, result]}
								<tr class="border-b border-gray-200">
									<td class="py-1.5 pr-4 text-gray-600">{method}</td>
									<td class="py-1.5 text-gray-600">{result}</td>
								</tr>
							{/each}
							{#each Object.entries(extraction.benchmark.proposed_results) as [method, result]}
								<tr class="border-b border-gray-200 bg-green-50">
									<td class="py-1.5 pr-4 text-green-800 font-medium">{method}</td>
									<td class="py-1.5 text-green-800 font-medium">{result}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		</div>
	{/if}

	<!-- Claims -->
	{#if extraction.claims.length > 0}
		<div>
			<h3 class="text-sm font-semibold text-gray-800 mb-3">주장 목록</h3>
			<div class="space-y-2">
				{#each extraction.claims as c}
					<div class="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
						<span class="text-xs font-mono font-semibold text-gray-500 mt-0.5 shrink-0">{c.claim_id}</span>
						<div class="flex-1">
							<p class="text-sm text-gray-700">{c.text}</p>
							<div class="flex gap-2 mt-1">
								<span class="text-xs px-2 py-0.5 rounded-full bg-gray-200 text-gray-600">{c.claim_type}</span>
								<span class="text-xs text-gray-500">confidence: {c.confidence}</span>
							</div>
						</div>
					</div>
				{/each}
			</div>
		</div>
	{/if}
</section>
