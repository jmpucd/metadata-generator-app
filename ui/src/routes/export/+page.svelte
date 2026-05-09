<script lang="ts">
	import { app } from '$lib/state.svelte';
	import { exportUrl, getStats } from '$lib/api';

	const approvedCount = $derived(app.stats.approved ?? 0);

	function download(format: 'csv' | 'json') {
		if (!app.selectedCollectionId) return;
		const url = exportUrl(app.selectedCollectionId, format);
		const a = document.createElement('a');
		a.href = url;
		a.download = `export.${format}`;
		a.click();
	}
</script>

<div class="export-page">
	<div class="export-inner">

		<span class="anno-label">Collection</span>
		<p class="col-name">{app.selectedCollection?.name ?? '—'}</p>

		<span class="anno-label">Approved records</span>
		<p class="stat-val">{approvedCount}</p>

		{#if approvedCount === 0}
			<p class="export-note">No approved records to export. Review and approve images first.</p>
		{:else}
			<div class="export-actions">
				<button class="btn-ghost active" onclick={() => download('csv')}>
					Export CSV
				</button>
				<button class="btn-ghost active" onclick={() => download('json')}>
					Export JSON
				</button>
			</div>

			<p class="export-note">
				CSV: tag fields (subjects, people, places, objects) are semicolon-separated.<br>
				JSON: tag fields are arrays.
			</p>
		{/if}

	</div>
</div>

<style>
	.export-page {
		height: 100vh;
		display: flex;
		align-items: flex-start;
		padding: 2rem 2.5rem;
		overflow-y: auto;
	}

	.export-inner {
		max-width: 400px;
		width: 100%;
	}

	.col-name {
		font-size: 1.1rem;
		font-weight: 300;
		letter-spacing: -0.01em;
		color: var(--c-text);
		margin-bottom: 1.5rem;
	}

	.stat-val {
		font-family: var(--font-mono);
		font-size: 2rem;
		color: var(--c-text);
		letter-spacing: -0.02em;
		margin-bottom: 2rem;
	}

	.export-actions {
		display: flex;
		gap: 1rem;
		margin-bottom: 1.5rem;
	}

	.export-note {
		font-size: 0.55rem;
		letter-spacing: 0.08em;
		color: var(--c-ghost);
		line-height: 1.8;
	}
</style>
