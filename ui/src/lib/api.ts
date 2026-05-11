import type { Collection, ImageEntry, MetadataRecord, RevisionEntry, StatusCounts } from './types';

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

// ── Images ────────────────────────────────────────────────────────────────────

export const getImages = (collectionId: number, status?: string) => {
	const qs = status && status !== 'all' ? `?status=${status}` : '';
	return req<ImageEntry[]>(`/collections/${collectionId}/images${qs}`);
};

export const imageFileUrl  = (id: number) => `${BASE}/images/${id}/file`;
export const thumbnailUrl  = (id: number) => `${BASE}/images/${id}/thumbnail`;

// ── Metadata ──────────────────────────────────────────────────────────────────

export const getMetadata = (imageId: number) =>
	req<MetadataRecord>(`/metadata/${imageId}`);

export const putMetadata = (imageId: number, fields: Partial<MetadataRecord>) =>
	req<MetadataRecord>(`/metadata/${imageId}`, {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(fields),
	});

export const setStatus = (imageId: number, status: string) =>
	req<{ image_id: number; status: string }>(`/metadata/${imageId}/status`, {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ status }),
	});

export const getHistory = (imageId: number) =>
	req<RevisionEntry[]>(`/metadata/${imageId}/history`);

// ── Revise ────────────────────────────────────────────────────────────────────

export const revise = (imageId: number, feedback: string) =>
	req<MetadataRecord>(`/metadata/${imageId}/revise`, {
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
