<script lang="ts">
	export let keyword: string;
	export let type: 'default' | 'custom' = 'default';
	export let source: string = '';
	export let disabled: boolean = false;
	export let onToggle: (() => void) | null = null;
	export let onRemove: (() => void) | null = null;

	const sourceColors: Record<string, string> = {
		manual: 'bg-blue-100 text-blue-800 border-blue-200',
		arxiv: 'bg-purple-100 text-purple-800 border-purple-200',
		freetext: 'bg-teal-100 text-teal-800 border-teal-200'
	};

	$: chipClass =
		type === 'custom'
			? sourceColors[source] || 'bg-gray-100 text-gray-800 border-gray-200'
			: disabled
				? 'bg-gray-100 text-gray-400 border-gray-200 line-through'
				: 'bg-indigo-100 text-indigo-800 border-indigo-200';
</script>

<span
	class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium border
			 transition-all {chipClass}"
>
	{keyword}

	{#if type === 'default' && onToggle}
		<button
			class="ml-1 w-5 h-5 rounded-full flex items-center justify-center
					 hover:bg-black/10 transition-colors text-xs"
			on:click={onToggle}
			title={disabled ? '활성화' : '비활성화'}
		>
			{disabled ? '+' : '-'}
		</button>
	{/if}

	{#if type === 'custom' && onRemove}
		<button
			class="ml-1 w-5 h-5 rounded-full flex items-center justify-center
					 hover:bg-black/10 transition-colors text-xs"
			on:click={onRemove}
			title="삭제"
		>
			x
		</button>
	{/if}
</span>
