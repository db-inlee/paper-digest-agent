<script lang="ts">
	import type { Scoring } from '$lib/types/paperDetail';

	export let scoring: Scoring;

	const recommendationLabels: Record<string, { label: string; color: string }> = {
		must_read: { label: 'Must Read', color: 'bg-green-600' },
		worth_reading: { label: 'Worth Reading', color: 'bg-blue-600' },
		skim: { label: 'Skim', color: 'bg-yellow-500' },
		skip: { label: 'Skip', color: 'bg-gray-500' }
	};

	$: rec = recommendationLabels[scoring.recommendation] ?? {
		label: scoring.recommendation,
		color: 'bg-gray-500'
	};

	function scoreBarWidth(score: number): string {
		return `${(score / 5) * 100}%`;
	}

	function scoreColor(score: number): string {
		if (score >= 4) return 'bg-green-500';
		if (score >= 3) return 'bg-blue-500';
		if (score >= 2) return 'bg-yellow-500';
		return 'bg-red-500';
	}

	const axes = [
		{ key: 'practicality' as const, label: '실용성 (Practicality)' },
		{ key: 'codeability' as const, label: '구현 가능성 (Codeability)' },
		{ key: 'signal' as const, label: '시그널 (Signal)' }
	];
</script>

<section class="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
	<div class="flex items-center justify-between mb-5">
		<h2 class="text-xl font-bold text-gray-900">평가 (Scoring)</h2>
		<span class="px-3 py-1 text-sm font-semibold text-white rounded-full {rec.color}">
			{rec.label}
		</span>
	</div>

	<!-- Score Bars -->
	<div class="space-y-4 mb-6">
		{#each axes as { key, label }}
			<div>
				<div class="flex justify-between text-sm mb-1">
					<span class="text-gray-700 font-medium">{label}</span>
					<span class="text-gray-500 font-semibold">{scoring[key]}/5</span>
				</div>
				<div class="h-3 bg-gray-200 rounded-full overflow-hidden">
					<div
						class="h-full rounded-full transition-all duration-300 {scoreColor(scoring[key])}"
						style="width: {scoreBarWidth(scoring[key])}"
					/>
				</div>
			</div>
		{/each}
	</div>

	<!-- Reasoning -->
	<p class="text-gray-700 text-sm leading-relaxed mb-4">{scoring.reasoning}</p>

	<!-- Key Strength & Main Concern -->
	<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
		<div class="p-4 bg-green-50 rounded-lg border border-green-200">
			<h4 class="text-sm font-semibold text-green-800 mb-1">핵심 강점</h4>
			<p class="text-sm text-green-700">{scoring.key_strength}</p>
		</div>
		<div class="p-4 bg-orange-50 rounded-lg border border-orange-200">
			<h4 class="text-sm font-semibold text-orange-800 mb-1">주요 우려</h4>
			<p class="text-sm text-orange-700">{scoring.main_concern}</p>
		</div>
	</div>
</section>
