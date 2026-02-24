import { writable } from 'svelte/store';

export type PipelineState = 'idle' | 'running' | 'completed' | 'error';

export interface PipelineStatus {
	state: PipelineState;
	date: string | null;
	error: string | null;
}

export const pipelineStatus = writable<PipelineStatus>({
	state: 'idle',
	date: null,
	error: null
});

const API_BASE = '/api';
let pollTimer: ReturnType<typeof setInterval> | null = null;

export async function triggerPipeline(date?: string): Promise<boolean> {
	try {
		const response = await fetch(`${API_BASE}/pipeline/run`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ date: date || null })
		});
		if (response.status === 409) return false;
		if (!response.ok) throw new Error('Failed to trigger pipeline');
		const data = await response.json();
		pipelineStatus.set({ state: data.state, date: data.date, error: null });
		startPolling();
		return true;
	} catch {
		return false;
	}
}

export async function fetchPipelineStatus(): Promise<void> {
	try {
		const response = await fetch(`${API_BASE}/pipeline/status`);
		if (!response.ok) return;
		const data: PipelineStatus = await response.json();
		pipelineStatus.set(data);
		if (data.state !== 'running') {
			stopPolling();
		}
	} catch {
		// ignore
	}
}

function startPolling() {
	stopPolling();
	pollTimer = setInterval(fetchPipelineStatus, 3000);
}

function stopPolling() {
	if (pollTimer) {
		clearInterval(pollTimer);
		pollTimer = null;
	}
}
