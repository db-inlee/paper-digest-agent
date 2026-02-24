<script lang="ts">
	import { page } from '$app/stores';
	import { userName } from '$lib/stores/votes';

	export let onOpenNameModal: () => void;

	$: currentPath = $page.url.pathname;
</script>

<header class="bg-white border-b border-gray-200 shrink-0 z-50">
	<div class="px-4 py-3 flex items-center justify-between">
		<div class="flex items-center gap-5">
			<!-- Logo -->
			<div class="flex items-center gap-2">
				<span class="text-xl">📚</span>
				<span class="text-lg font-bold text-gray-900">Paper Digest</span>
			</div>

			<!-- Tabs -->
			<nav class="flex items-center gap-1 ml-2">
				<a
					href="/"
					class="px-3 py-1.5 text-sm font-medium rounded-lg transition-colors
							 {currentPath === '/' || currentPath.startsWith('/paper')
								? 'bg-indigo-50 text-indigo-700'
								: 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'}"
				>
					📄 논문 보기
				</a>
				<a
					href="/add"
					class="px-3 py-1.5 text-sm font-medium rounded-lg transition-colors
							 {currentPath === '/add'
								? 'bg-indigo-50 text-indigo-700'
								: 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'}"
				>
					📥 논문 추가
				</a>
				<a
					href="/topics"
					class="px-3 py-1.5 text-sm font-medium rounded-lg transition-colors
							 {currentPath === '/topics'
								? 'bg-indigo-50 text-indigo-700'
								: 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'}"
				>
					⚙️ 관심사 설정
				</a>
			</nav>
		</div>

		<div class="flex items-center gap-3">
			<!-- User Name -->
			<button
				class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-opacity hover:opacity-80
						 {$userName ? 'bg-indigo-50 text-indigo-700' : 'bg-yellow-50 text-yellow-700'}"
				on:click={onOpenNameModal}
			>
				<span>{$userName ? '👤' : '⚠️'}</span>
				<span>{$userName || '닉네임 설정'}</span>
			</button>
		</div>
	</div>
</header>
