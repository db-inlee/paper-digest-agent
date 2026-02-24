<script lang="ts">
	import type { Delta } from '$lib/types/paperDetail';

	export let delta: Delta;
</script>

<section class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
	<h2 class="text-xl font-bold text-gray-900 mb-2">핵심 차별점 (Delta)</h2>

	<!-- One-line takeaway -->
	<p class="text-indigo-700 font-medium bg-indigo-50 rounded-lg p-3 mb-6 text-sm leading-relaxed">
		{delta.one_line_takeaway}
	</p>

	<!-- Core Deltas -->
	{#if delta.core_deltas.length > 0}
		<div class="space-y-4 mb-6">
			{#each delta.core_deltas as d}
				<div class="border border-gray-200 rounded-lg overflow-hidden">
					<div class="bg-gray-50 px-4 py-2">
						<span class="text-sm font-semibold text-gray-800">{d.axis}</span>
					</div>
					<div class="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-gray-200">
						<div class="p-4">
							<span class="text-xs font-semibold text-red-500 uppercase tracking-wider">Before</span>
							<p class="text-sm text-gray-700 mt-1">{d.old_approach}</p>
						</div>
						<div class="p-4">
							<span class="text-xs font-semibold text-green-600 uppercase tracking-wider">After</span>
							<p class="text-sm text-gray-700 mt-1">{d.new_approach}</p>
						</div>
					</div>
					<div class="bg-blue-50 px-4 py-2">
						<p class="text-sm text-blue-700"><strong>Why better:</strong> {d.why_better}</p>
					</div>
				</div>
			{/each}
		</div>
	{/if}

	<!-- Tradeoffs -->
	{#if delta.tradeoffs.length > 0}
		<div class="mb-6">
			<h3 class="text-sm font-semibold text-gray-800 mb-3">트레이드오프</h3>
			<div class="space-y-3">
				{#each delta.tradeoffs as t}
					<div class="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
						<p class="text-sm font-semibold text-yellow-800 mb-1">{t.aspect}</p>
						<div class="text-sm text-gray-700 space-y-1">
							<p><span class="text-green-700 font-medium">Benefit:</span> {t.benefit}</p>
							<p><span class="text-red-600 font-medium">Cost:</span> {t.cost}</p>
							<p><span class="text-gray-500 font-medium">Acceptable when:</span> {t.when_acceptable}</p>
						</div>
					</div>
				{/each}
			</div>
		</div>
	{/if}

	<!-- When to use / not -->
	<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
		<div class="p-4 bg-green-50 rounded-lg border border-green-200">
			<h4 class="text-sm font-semibold text-green-800 mb-1">사용 권장</h4>
			<p class="text-sm text-green-700">{delta.when_to_use}</p>
		</div>
		<div class="p-4 bg-red-50 rounded-lg border border-red-200">
			<h4 class="text-sm font-semibold text-red-800 mb-1">사용 비권장</h4>
			<p class="text-sm text-red-700">{delta.when_not_to_use}</p>
		</div>
	</div>
</section>
