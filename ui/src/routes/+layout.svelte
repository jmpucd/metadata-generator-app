<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { getCollections, getStats } from '$lib/api';
	import { app } from '$lib/state.svelte';

	let { children } = $props();

	const STATUS_OPTIONS = [
		{ value: 'all',          label: 'All' },
		{ value: 'needs_review', label: 'Needs review' },
		{ value: 'in_progress',  label: 'In progress' },
		{ value: 'revised',      label: 'Revised' },
		{ value: 'approved',     label: 'Approved' },
		{ value: 'flagged',      label: 'Flagged' },
	];

	async function loadCollections() {
		app.collections = await getCollections();
		if (app.collections.length && app.selectedCollectionId === null) {
			app.selectedCollectionId = app.collections[0].id;
		}
	}

	async function refreshStats() {
		if (app.selectedCollectionId !== null) {
			app.stats = await getStats(app.selectedCollectionId);
		}
	}

	$effect(() => {
		if (app.selectedCollectionId !== null) refreshStats();
	});

	onMount(loadCollections);

	const STATUS_LABELS: Record<string, string> = {
		needs_review: 'Needs review',
		in_progress:  'In progress',
		revised:      'Revised',
		approved:     'Approved',
		flagged:      'Flagged',
	};

	function pad(n: number | undefined) {
		return String(n ?? 0).padStart(3, '0');
	}

	const navLinks = [
		{ href: '/review', label: 'Review' },
		{ href: '/grid',   label: 'Grid' },
		{ href: '/setup',  label: 'Setup' },
		{ href: '/export', label: 'Export' },
	];
</script>

<div class="shell">
	<aside class="sidebar">
		<div class="sidebar-brand">
			Metadata<br>Generator
		</div>

		<div class="sidebar-section">
			<span class="sidebar-label">Collection</span>
			<select
				value={app.selectedCollectionId ?? ''}
				onchange={(e) => {
					app.selectedCollectionId = Number((e.target as HTMLSelectElement).value);
				}}
			>
				{#each app.collections as col}
					<option value={col.id}>{col.name}</option>
				{/each}
			</select>
		</div>

		<div class="sidebar-section">
			<span class="sidebar-label">Filter</span>
			<select
				value={app.statusFilter}
				onchange={(e) => {
					app.statusFilter = (e.target as HTMLSelectElement).value;
				}}
			>
				{#each STATUS_OPTIONS as opt}
					<option value={opt.value}>{opt.label}</option>
				{/each}
			</select>
		</div>

		<div class="sidebar-counts">
			{#each Object.entries(STATUS_LABELS) as [key, label]}
				<div class="count-row">
					<span class="count-label">{label}</span>
					<span class="count-val">{pad(app.stats[key as keyof typeof app.stats])}</span>
				</div>
			{/each}
		</div>

		<nav class="sidebar-nav">
			{#each navLinks as link}
				<a
					href={link.href}
					class:active={$page.url.pathname.startsWith(link.href)}
				>{link.label}</a>
			{/each}
		</nav>
	</aside>

	<main class="page">
		{@render children()}
	</main>
</div>
