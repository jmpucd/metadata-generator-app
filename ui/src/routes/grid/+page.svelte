<script lang="ts">
	import { goto } from '$app/navigation';
	import { app } from '$lib/state.svelte';
	import { getImages } from '$lib/api';
	import { thumbnailUrl } from '$lib/api';

	// load images whenever collection or filter changes
	$effect(() => {
		const colId = app.selectedCollectionId;
		const filter = app.statusFilter;
		if (colId === null) return;
		getImages(colId, filter).then(imgs => { app.images = imgs; });
	});

	function open(index: number) {
		app.currentIndex = index;
		goto('/review');
	}

	function handleKey(e: KeyboardEvent) {
		if (e.key === 'Escape') goto('/review');
	}

	const STATUS_COLOR: Record<string, string> = {
		needs_review: 'var(--c-ghost-lt)',
		in_progress:  'var(--c-ghost)',
		revised:      'var(--c-muted)',
		approved:     'var(--c-text)',
		flagged:      'var(--c-text)',
	};
</script>

<svelte:window onkeydown={handleKey} />

<div class="grid-page">
	{#if !app.images.length}
		<div class="grid-empty">No images.</div>
	{:else}
		<div class="grid">
			{#each app.images as img, i}
				<button
					class="cell"
					class:is-approved={img.status === 'approved'}
					class:is-flagged={img.status === 'flagged'}
					onclick={() => open(i)}
					title={img.filename}
				>
					<div class="thumb-wrap">
						<img
							src={thumbnailUrl(img.id)}
							alt={img.filename}
							class="thumb"
							loading="lazy"
						/>
					</div>
					<div class="cell-meta">
						<span class="cell-name">{img.filename}</span>
						<span
							class="cell-dot"
							style="background: {STATUS_COLOR[img.status] ?? 'var(--c-ghost-lt)'}"
						></span>
					</div>
				</button>
			{/each}
		</div>
	{/if}
</div>

<style>
	.grid-page {
		height: 100vh;
		overflow-y: auto;
		padding: 1.5rem;
	}
	.grid-page::-webkit-scrollbar { width: 4px; }
	.grid-page::-webkit-scrollbar-thumb { background: var(--c-border); }

	.grid-empty {
		height: 100%;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 0.6rem;
		letter-spacing: 0.16em;
		text-transform: uppercase;
		color: var(--c-ghost);
	}

	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
		gap: 1px;
		background: var(--c-border-subtle);
	}

	.cell {
		background: var(--c-bg);
		border: none;
		padding: 0;
		cursor: pointer;
		display: flex;
		flex-direction: column;
		text-align: left;
		transition: background 0.1s;
	}
	.cell:hover { background: var(--c-sidebar-bg); }
	.cell:hover .thumb { opacity: 0.85; }

	.cell.is-approved .cell-dot { opacity: 1; }
	.cell.is-flagged  .thumb-wrap { outline: 1px solid var(--c-text); outline-offset: -1px; }

	.thumb-wrap {
		width: 100%;
		aspect-ratio: 4 / 3;
		overflow: hidden;
		background: var(--c-border-subtle);
	}
	.thumb {
		width: 100%;
		height: 100%;
		object-fit: cover;
		display: block;
		transition: opacity 0.1s;
	}

	.cell-meta {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.35rem 0.5rem;
		gap: 0.4rem;
	}
	.cell-name {
		font-family: var(--font-mono);
		font-size: 0.5rem;
		color: var(--c-muted);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		flex: 1;
	}
	.cell-dot {
		width: 5px;
		height: 5px;
		border-radius: 50%;
		flex-shrink: 0;
		opacity: 0.6;
	}
</style>
