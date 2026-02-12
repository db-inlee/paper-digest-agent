<script lang="ts">
	import '../app.css';
	import { page } from '$app/stores';
	import { userName, slackUserId } from '$lib/stores/votes';
	import TopNavBar from '$lib/components/TopNavBar.svelte';
	import Sidebar from '$lib/components/Sidebar.svelte';

	interface SlackMember {
		id: string;
		name: string;
		display_name: string;
		avatar: string;
	}

	let showNameModal = false;
	let tempName = '';
	let slackMembers: SlackMember[] = [];
	let slackLoading = false;
	let slackConnected = false;

	async function fetchSlackMembers() {
		slackLoading = true;
		try {
			const resp = await fetch('/api/slack/members');
			const data = await resp.json();
			slackMembers = data.members || [];
			slackConnected = data.slack_connected || false;
		} catch {
			slackMembers = [];
			slackConnected = false;
		}
		slackLoading = false;
	}

	function openNameModal() {
		tempName = $userName;
		showNameModal = true;
		fetchSlackMembers();
	}

	function selectSlackMember(member: SlackMember) {
		userName.set(member.display_name);
		slackUserId.set(member.id);
		showNameModal = false;
	}

	function saveName() {
		if (tempName.trim()) {
			userName.set(tempName.trim());
			slackUserId.set('');  // Clear Slack ID when using manual name
		}
		showNameModal = false;
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Enter') {
			saveName();
		} else if (event.key === 'Escape') {
			showNameModal = false;
		}
	}

	$: hideSidebar = $page.url.pathname === '/topics' || $page.url.pathname === '/add';
</script>

<div class="h-screen flex flex-col">
	<TopNavBar onOpenNameModal={openNameModal} />

	<div class="flex flex-1 overflow-hidden">
		{#if !hideSidebar}
			<Sidebar />
		{/if}

		<main class="flex-1 overflow-y-auto p-6">
			<slot />
		</main>
	</div>
</div>

<!-- Name Modal -->
{#if showNameModal}
	<div
		class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
		on:click|self={() => (showNameModal = false)}
		on:keydown={handleKeydown}
		role="dialog"
		tabindex="-1"
	>
		<div class="bg-white rounded-xl shadow-xl p-6 w-full max-w-sm mx-4">
			<h2 class="text-lg font-semibold mb-4">닉네임 설정</h2>

			{#if slackLoading}
				<p class="text-sm text-gray-500 mb-4">Slack 연동 확인 중...</p>
			{:else if slackMembers.length > 0}
				<!-- Slack member picker -->
				<p class="text-sm text-gray-600 mb-3">Slack 계정으로 로그인</p>
				<div class="max-h-48 overflow-y-auto border border-gray-200 rounded-lg mb-4">
					{#each slackMembers as member}
						<button
							class="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-indigo-50 transition-colors text-left
									 {$slackUserId === member.id ? 'bg-indigo-50 border-l-2 border-indigo-500' : ''}"
							on:click={() => selectSlackMember(member)}
						>
							{#if member.avatar}
								<img src={member.avatar} alt="" class="w-8 h-8 rounded-full" />
							{:else}
								<div class="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center text-sm">
									{member.display_name.charAt(0)}
								</div>
							{/if}
							<span class="text-sm font-medium text-gray-800">{member.display_name}</span>
						</button>
					{/each}
				</div>

				<div class="relative my-4">
					<div class="absolute inset-0 flex items-center"><div class="w-full border-t border-gray-200"></div></div>
					<div class="relative flex justify-center"><span class="bg-white px-3 text-xs text-gray-400">또는 직접 입력</span></div>
				</div>
			{/if}

			<p class="text-sm text-gray-600 mb-2">
				{slackMembers.length > 0 ? '' : '투표 시 표시될 닉네임을 입력하세요.'}
			</p>
			<input
				type="text"
				bind:value={tempName}
				placeholder="닉네임 입력"
				class="w-full px-3 py-2 border border-gray-300 rounded-lg mb-4
						 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
				on:keydown={handleKeydown}
			/>
			<div class="flex justify-end gap-3">
				<button
					class="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
					on:click={() => (showNameModal = false)}
				>
					취소
				</button>
				<button
					class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
					on:click={saveName}
				>
					저장
				</button>
			</div>
		</div>
	</div>
{/if}
