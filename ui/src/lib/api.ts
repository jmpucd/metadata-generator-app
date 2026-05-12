import type { Collection, ItemEntry, MetadataRecord, RevisionEntry, StatusCounts } from './types';

const BASE = '/api';

async function req<T>(url: string, opts?: RequestInit): Promise<T> {
	const r = await fetch(BASE + url, opts);
	if (!r.ok) {
		const text = await r.text().catch(() => r.statusText);
		throw new Error(`${opts?.method ?? 'GET'} ${url} → ${r.status}: ${text}`);
	}
	return r.json();
}

// ── Collections ───────────────────────────────────────────────────────────────

export const getCollections = () =>
	req<Collection[]>('/collections');

export const createCollection = (body: Partial<Collection>) =>
	req<Collection>('/collections', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body),
	});

export const updateCollection = (id: number, body: Partial<Collection>) =>
	req<Collection>(`/collections/${id}`, {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body),
	});

export const getStats = (collectionId: number) =>
	req<StatusCounts>(`/collections/${collectionId}/stats`);

// ── Items ─────────────────────────────────────────────────────────────────────

export const getItems = (collectionId: number, status?: string) => {
	const qs = status && status !== 'all' ? `?status=${status}` : '';
	return req<ItemEntry[]>(`/collections/${collectionId}/items${qs}`);
};

// ── Images (file serving) ─────────────────────────────────────────────────────

export const imageFileUrl = (id: number) => `${BASE}/images/${id}/file`;
export const thumbnailUrl = (id: number) => `${BASE}/images/${id}/thumbnail`;

// ── Metadata ──────────────────────────────────────────────────────────────────

export const getMetadata = (itemId: number) =>
	req<MetadataRecord>(`/metadata/${itemId}`);

export const putMetadata = (itemId: number, fields: Partial<MetadataRecord>) =>
	req<MetadataRecord>(`/metadata/${itemId}`, {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(fields),
	});

export const setStatus = (itemId: number, status: string) =>
	req<{ item_id: number; status: string }>(`/metadata/${itemId}/status`, {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ status }),
	});

export const getHistory = (itemId: number) =>
	req<RevisionEntry[]>(`/metadata/${itemId}/history`);

// ── Revise ────────────────────────────────────────────────────────────────────

export const revise = (itemId: number, feedback: string) =>
	req<MetadataRecord>(`/metadata/${itemId}/revise`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ feedback }),
	});

// ── Config ────────────────────────────────────────────────────────────────────

export const getConfig = () =>
	req<{ backend: string; model: string }>('/config');

// ── Export ────────────────────────────────────────────────────────────────────

export const exportUrl = (collectionId: number, format: 'csv' | 'json' = 'csv') =>
	`${BASE}/collections/${collectionId}/export?format=${format}`;
