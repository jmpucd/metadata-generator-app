<script lang="ts">
	import { app } from '$lib/state.svelte';
	import { createCollection, updateCollection, getCollections, generateCollection, getPromptPacks } from '$lib/api';
	import type { Collection, PromptPack } from '$lib/types';

	type Mode = 'view' | 'edit' | 'new';
	let mode = $state<Mode>('view');
	let saving = $state(false);
	let generating = $state(false);
	let generateMsg = $state('');
	let error = $state('');

	// form fields
	let name                  = $state('');
	let description_style     = $state('');
	let controlled_vocabulary = $state('');
	let known_locations       = $state('');
	let known_date_range      = $state('');
	let known_people_orgs     = $state('');
	let terms_to_avoid        = $state('');
	let institutional_rules   = $state('');
	let rights_sensitivity    = $state('');
	let selectedPacks         = $state<string[]>([]);

	let availablePacks = $state<PromptPack[]>([]);
	getPromptPacks().then(p => availablePacks = p).catch(() => availablePacks = []);

	function togglePack(name: string) {
		selectedPacks = selectedPacks.includes(name)
			? selectedPacks.filter(p => p !== name)
			: [...selectedPacks, name];
	}

	function loadCollection(col: Collection) {
		name                  = col.name ?? '';
		description_style     = col.description_style ?? '';
		controlled_vocabulary = col.controlled_vocabulary ?? '';
		known_locations       = col.known_locations ?? '';
		known_date_range      = col.known_date_range ?? '';
		known_people_orgs     = col.known_people_orgs ?? '';
		terms_to_avoid        = col.terms_to_avoid ?? '';
		institutional_rules   = col.institutional_rules ?? '';
		rights_sensitivity    = col.rights_sensitivity_notes ?? '';
		selectedPacks         = (col.prompt_packs ?? '').split(',').map(p => p.trim()).filter(Boolean);
	}

	function startEdit() {
		if (app.selectedCollection) loadCollection(app.selectedCollection);
		mode = 'edit';
		error = '';
	}

	function startNew() {
		name = description_style = controlled_vocabulary = known_locations =
		known_date_range = known_people_orgs = terms_to_avoid =
		institutional_rules = rights_sensitivity = '';
		selectedPacks = [];
		mode = 'new';
		error = '';
	}

	function cancel() { mode = 'view'; error = ''; }

	async function submitAndGenerate() {
		await submit();
		if (error) return;
		const id = app.selectedCollectionId;
		if (id === null) return;
		generating = true;
		generateMsg = '';
		try {
			await generateCollection(id);
			generateMsg = 'Generation started — check the Review page for results.';
		} catch {
			generateMsg = 'Saved, but failed to start generation.';
		} finally {
			generating = false;
		}
	}

	async function submit() {
		if (!name.trim()) { error = 'Name is required.'; return; }
		saving = true;
		error = '';
		try {
			const body = {
				name:                     name.trim(),
				description_style:        description_style || null,
				controlled_vocabulary:    controlled_vocabulary || null,
				known_locations:          known_locations || null,
				known_date_range:         known_date_range || null,
				known_people_orgs:        known_people_orgs || null,
				terms_to_avoid:           terms_to_avoid || null,
				institutional_rules:      institutional_rules || null,
				rights_sensitivity_notes: rights_sensitivity || null,
				prompt_packs:             selectedPacks.join(', ') || null,
			};
			if (mode === 'new') {
				const created = await createCollection(body);
				app.collections = await getCollections();
				app.selectedCollectionId = created.id;
			} else if (app.selectedCollectionId !== null) {
				await updateCollection(app.selectedCollectionId, body);
				app.collections = await getCollections();
			}
			mode = 'view';
		} catch (e: unknown) {
			error = e instanceof Error ? e.message : 'Save failed.';
		} finally {
			saving = false;
		}
	}

	function autosize(node: HTMLTextAreaElement) {
		function resize() { node.style.height = 'auto'; node.style.height = node.scrollHeight + 'px'; }
		resize();
		node.addEventListener('input', resize);
		return { destroy() { node.removeEventListener('input', resize); } };
	}

	const col = $derived(app.selectedCollection);
</script>

<div class="setup-page">
	<div class="setup-inner">

		{#if mode === 'view'}
			{#if col}
				<div class="view-header">
					<h1 class="col-name">{col.name}</h1>
					<button class="btn-ghost" onclick={startEdit}>Edit</button>
				</div>

				{#each [
					['Description style', col.description_style],
					['Controlled vocabulary', col.controlled_vocabulary],
					['Known locations', col.known_locations],
					['Known date range', col.known_date_range],
					['Known people / orgs', col.known_people_orgs],
					['Terms to avoid', col.terms_to_avoid],
					['Institutional rules', col.institutional_rules],
					['Rights & sensitivity', col.rights_sensitivity_notes],
					['Prompt packs', col.prompt_packs],
				] as [label, val]}
					{#if val}
						<span class="anno-label">{label}</span>
						<p class="view-val">{val}</p>
					{/if}
				{/each}

				<div class="view-footer">
					<button class="btn-ghost" onclick={startNew}>New collection</button>
				</div>
			{:else}
				<div class="setup-empty">
					<p>No collections yet.</p>
					<button class="btn-ghost active" onclick={startNew}>Create one</button>
				</div>
			{/if}

		{:else}
			<div class="form-header">
				<h1 class="col-name">{mode === 'new' ? 'New collection' : 'Edit collection'}</h1>
			</div>

			<span class="anno-label">Name</span>
			<input class="field-input title" bind:value={name} placeholder="Collection name" />

			<span class="anno-label">Description style</span>
			<textarea class="field-textarea" bind:value={description_style} use:autosize
				placeholder="How should descriptions be written? Tone, tense, length…"></textarea>

			<span class="anno-label">Controlled vocabulary</span>
			<textarea class="field-textarea" bind:value={controlled_vocabulary} use:autosize
				placeholder="Subject headings, thesauri, or term lists to draw from…"></textarea>

			<span class="anno-label">Known locations</span>
			<input class="field-input" bind:value={known_locations} placeholder="—" />

			<span class="anno-label">Known date range</span>
			<input class="field-input" bind:value={known_date_range} placeholder="e.g. 1920–1945" />

			<span class="anno-label">Known people / organizations</span>
			<textarea class="field-textarea" bind:value={known_people_orgs} use:autosize placeholder="—"></textarea>

			<span class="anno-label">Terms to avoid</span>
			<textarea class="field-textarea" bind:value={terms_to_avoid} use:autosize placeholder="—"></textarea>

			<span class="anno-label">Institutional rules</span>
			<textarea class="field-textarea" bind:value={institutional_rules} use:autosize placeholder="—"></textarea>

			<span class="anno-label">Rights & sensitivity notes</span>
			<textarea class="field-textarea" bind:value={rights_sensitivity} use:autosize placeholder="—"></textarea>

			<span class="anno-label">Prompt packs</span>
			{#if availablePacks.length}
				<div class="pack-list">
					{#each availablePacks as pack}
						<label class="pack">
							<input type="checkbox" checked={selectedPacks.includes(pack.name)}
								onchange={() => togglePack(pack.name)} />
							<span class="pack-body">
								<span class="pack-name">{pack.name}</span>
								<span class="pack-applies">{pack.applies_to.join(' · ')}</span>
								{#if pack.description}<span class="pack-desc">{pack.description}</span>{/if}
							</span>
						</label>
					{/each}
				</div>
			{:else}
				<p class="pack-empty">No packs found in prompts/packs/.</p>
			{/if}

			{#if error}
				<p class="form-error">{error}</p>
			{/if}

			<div class="form-actions">
				<button class="btn-ghost" onclick={cancel}>Cancel</button>
				<button class="btn-ghost active" onclick={submit} disabled={saving || generating}>
					{saving ? 'Saving…' : 'Save'}
				</button>
				{#if mode === 'edit'}
				<button class="btn-ghost active" onclick={submitAndGenerate} disabled={saving || generating}>
					{generating ? 'Starting…' : 'Save & Regenerate'}
				</button>
				{/if}
			</div>
			{#if generateMsg}<p class="generate-msg">{generateMsg}</p>{/if}
		{/if}

	</div>
</div>

<style>
	.generate-msg {
		font-size: 0.8rem;
		opacity: 0.7;
		margin-top: 0.5rem;
	}

	.setup-page {
		height: 100vh;
		overflow-y: auto;
		padding: 2rem 2.5rem;
	}
	.setup-page::-webkit-scrollbar { width: 4px; }
	.setup-page::-webkit-scrollbar-thumb { background: var(--c-border); }

	.setup-inner {
		max-width: 560px;
	}

	.view-header, .form-header {
		display: flex;
		align-items: baseline;
		gap: 1rem;
		margin-bottom: 1.5rem;
	}

	.col-name {
		font-size: 1.1rem;
		font-weight: 300;
		letter-spacing: -0.01em;
		color: var(--c-text);
		flex: 1;
	}

	.view-val {
		font-size: 0.8rem;
		color: var(--c-text-body);
		line-height: 1.65;
		margin-bottom: 1rem;
		white-space: pre-wrap;
	}

	.view-footer {
		margin-top: 2.5rem;
		padding-top: 1rem;
		border-top: 1px solid var(--c-border-subtle);
	}

	.setup-empty {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		padding-top: 3rem;
		color: var(--c-ghost);
		font-size: 0.6rem;
		letter-spacing: 0.14em;
		text-transform: uppercase;
	}

	.form-actions {
		display: flex;
		gap: 0.5rem;
		margin-top: 2rem;
	}

	.pack-list {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
		margin-bottom: 1rem;
	}

	.pack {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
		cursor: pointer;
	}

	.pack input { margin-top: 0.2rem; }

	.pack-body {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}

	.pack-name {
		font-size: 0.8rem;
		color: var(--c-text);
	}

	.pack-applies {
		font-size: 0.55rem;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--c-ghost);
	}

	.pack-desc {
		font-size: 0.75rem;
		color: var(--c-text-body);
		line-height: 1.5;
	}

	.pack-empty {
		font-size: 0.75rem;
		color: var(--c-ghost);
		margin-bottom: 1rem;
	}

	.form-error {
		font-size: 0.6rem;
		color: var(--c-text);
		letter-spacing: 0.08em;
		margin-top: 0.75rem;
	}
</style>
