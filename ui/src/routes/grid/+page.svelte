<script lang="ts">
	import { goto } from '$app/navigation';
	import { app } from '$lib/state.svelte';
	import { getItems, thumbnailUrl } from '$lib/api';

	$effect(() => {
		const colId = app.selectedCollectionId;
		const filter = app.statusFilter;
		if (colId === null) return;
		getItems(colId, filter).then(items => { app.items = items; });
	});

	function open(index: number) {
		app.currentIndex = index;
		goto('/review');
	}

	function handleKey(e: KeyboardEvent) {
		if (e.key === 'Escape') goto('/review');
	}

	const STATUS_COLOR: Record<string, string> = {
		queue:    'var(--c-ghost-lt)',
		working:  'var(--c-ghost)',
		ready:    'var(--c-text)',
		hold:     'var(--c-muted)',
		exported: 'var(--c-text)',
	};
</script>

<svelte:window onkeydown={handleKey} />

<div class="grid-page">
	{#if !app.items.length}
		<div class="grid-empty">No items.</div>
	{:else}
		<div class="grid">
			{#each app.items as item, i}
				<button
					class="cell"
					class:is-approved={item.status === 'approved'}
					class:is-flagged={item.status === 'flagged'}
					onclick={() => open(i)}
					title={item.item_key}
				>
					<div class="thumb-wrap">
						{#if item.pages.length}
							<img
								src={thumbnailUrl(item.pages[0].id)}
								alt={item.item_key}
								class="thumb"
								loading="lazy"
							/>
						{/if}
					</div>
					<div class="cell-meta">
						<span class="cell-name">{item.item_key}</span>
						{#if item.pages.length > 1}
							<span class="cell-pages">{item.pages.length}p</span>
						{/if}
						<span
							class="cell-dot"
							style="background: {STATUS_COLOR[item.status] ?? 'var(--c-ghost-lt)'}"
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
	.cell-pages {
		font-family: var(--font-mono);
		font-size: 0.42rem;
		color: var(--c-ghost);
		white-space: nowrap;
	}
	.cell-dot {
		width: 5px;
		height: 5px;
		border-radius: 50%;
		flex-shrink: 0;
		opacity: 0.6;
	}
</style>
