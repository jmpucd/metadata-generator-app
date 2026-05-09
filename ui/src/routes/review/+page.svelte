<script lang="ts">
	import { app } from '$lib/state.svelte';
	import {
		getImages, getMetadata, putMetadata, setStatus, revise,
		imageFileUrl, getStats,
	} from '$lib/api';
	import type { MetadataRecord } from '$lib/types';

	type Mode = 'study' | 'cataloging';

	let mode           = $state<Mode>('cataloging');
	let panelOpen      = $state(true);
	let reviseFeedback = $state('');
	let loadingImage   = $state(false);

	let title          = $state('');
	let description    = $state('');
	let subjects       = $state('');
	let visibleText    = $state('');
	let people         = $state('');
	let places         = $state('');
	let dates          = $state('');
	let objects        = $state('');
	let uncertainty    = $state('');
	let reviewerNotes  = $state('');
	let dirty          = $state(false);

	$effect(() => {
		const colId  = app.selectedCollectionId;
		const filter = app.statusFilter;
		if (colId === null) return;
		getImages(colId, filter).then(imgs => {
			app.images = imgs;
			app.currentIndex = 0;
			if (imgs.length) loadMeta(imgs[0].id);
			else app.currentMetadata = null;
		});
	});

	$effect(() => {
		const img = app.currentImage;
		if (!img) return;
		loadMeta(img.id);
	});

	async function loadMeta(imageId: number) {
		loadingImage = true;
		try {
			const meta = await getMetadata(imageId);
			app.currentMetadata = meta;
			syncFields(meta);
			dirty = false;
			if (meta.review_status === 'needs_review') {
				await setStatus(imageId, 'in_progress');
				meta.review_status = 'in_progress';
				const img = app.images.find(i => i.id === imageId);
				if (img) img.status = 'in_progress';
			}
		} finally {
			loadingImage = false;
		}
	}

	function syncFields(meta: MetadataRecord) {
		title         = meta.title ?? '';
		description   = meta.description ?? '';
		subjects      = (meta.subjects ?? []).join(', ');
		visibleText   = meta.visible_text ?? '';
		people        = (meta.people ?? []).join(', ');
		places        = (meta.places ?? []).join(', ');
		dates         = meta.dates ?? '';
		objects       = (meta.objects ?? []).join(', ');
		uncertainty   = meta.uncertainty_notes ?? '';
		reviewerNotes = meta.reviewer_notes ?? '';
	}

	function splitTag(s: string): string[] {
		return s.split(',').map(x => x.trim()).filter(Boolean);
	}

	function markDirty() { dirty = true; }

	async function save() {
		const img = app.currentImage;
		if (!img || app.saving) return;
		app.saving = true;
		try {
			const updated = await putMetadata(img.id, {
				title:             title || null,
				description:       description || null,
				visible_text:      visibleText || null,
				subjects:          splitTag(subjects),
				people:            splitTag(people),
				places:            splitTag(places),
				dates:             dates || null,
				objects:           splitTag(objects),
				uncertainty_notes: uncertainty || null,
				reviewer_notes:    reviewerNotes || null,
			});
			app.currentMetadata = updated;
			dirty = false;
		} finally {
			app.saving = false;
		}
	}

	function go(delta: number) {
		const next = app.currentIndex + delta;
		if (next < 0 || next >= app.total) return;
		app.currentIndex = next;
	}

	async function approve() {
		const img = app.currentImage;
		if (!img) return;
		await setStatus(img.id, 'approved');
		img.status = 'approved';
		if (app.currentMetadata) app.currentMetadata.review_status = 'approved';
		if (app.selectedCollectionId !== null) app.stats = await getStats(app.selectedCollectionId);
		go(1);
	}

	async function flag() {
		const img = app.currentImage;
		if (!img) return;
		await setStatus(img.id, 'flagged');
		img.status = 'flagged';
		if (app.currentMetadata) app.currentMetadata.review_status = 'flagged';
	}

	async function submitRevise() {
		const img = app.currentImage;
		if (!img || !reviseFeedback.trim() || app.revising) return;
		app.revising = true;
		try {
			const updated = await revise(img.id, reviseFeedback);
			app.currentMetadata = updated;
			syncFields(updated);
			dirty = false;
			reviseFeedback = '';
		} finally {
			app.revising = false;
		}
	}

	function handleKey(e: KeyboardEvent) {
		const tag = (e.target as HTMLElement).tagName;
		const inInput = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';

		if ((e.ctrlKey || e.metaKey) && e.key === 's') {
			e.preventDefault();
			save();
			return;
		}
		if (inInput) return;

		switch (e.key) {
			case 'ArrowRight':
			case 'j': go(1);                          break;
			case 'ArrowLeft':
			case 'k': go(-1);                         break;
			case 'a': approve();                       break;
			case 'f': flag();                          break;
			case 's': save();                          break;
			case 'm': mode = mode === 'study' ? 'cataloging' : 'study'; break;
			case 'p': panelOpen = !panelOpen;          break;
		}
	}

	function autosize(node: HTMLTextAreaElement) {
		function resize() {
			node.style.height = 'auto';
			node.style.height = node.scrollHeight + 'px';
		}
		resize();
		node.addEventListener('input', resize);
		return { destroy() { node.removeEventListener('input', resize); } };
	}

	const STATUS_LABEL: Record<string, string> = {
		needs_review: 'Needs review',
		in_progress:  'In progress',
		revised:      'Revised',
		approved:     'Approved',
		flagged:      'Flagged',
	};

	const hasPrev = $derived(app.currentIndex > 0);
	const hasNext = $derived(app.currentIndex < app.total - 1);
</script>

<svelte:window onkeydown={handleKey} />

{#if !app.currentImage}
	<div class="empty-state">
		{#if app.selectedCollectionId === null}
			Select a collection to begin.
		{:else}
			No images match this filter.
		{/if}
	</div>
{:else}
	<div class="review-shell" class:is-study={mode === 'study'} class:is-cataloging={mode === 'cataloging'}>

		<!-- ── image viewer ──────────────────────────────────────────────────── -->
		<div class="viewer">

			<!-- provenance strip -->
			<div class="viewer-strip">
				<span class="strip-col">{app.selectedCollection?.name ?? ''}</span>
				<span class="strip-sep">·</span>
				<span class="strip-file">{app.currentImage.filename}</span>
				{#if app.currentMetadata}
					<span class="badge badge-{app.currentMetadata.review_status}">
						{STATUS_LABEL[app.currentMetadata.review_status] ?? app.currentMetadata.review_status}
					</span>
				{/if}
			</div>

			<!-- image with inline navigation zones -->
			<div class="image-frame">
				<button
					class="nav-zone nav-prev"
					onclick={() => go(-1)}
					disabled={!hasPrev}
					aria-label="Previous image"
				>
					<span class="nav-arrow">←</span>
				</button>

				{#if loadingImage}
					<span class="spinner"></span>
				{:else}
					<img
						src={imageFileUrl(app.currentImage.id)}
						alt={app.currentMetadata?.title ?? app.currentImage.filename}
						class="main-img"
					/>
				{/if}

				<button
					class="nav-zone nav-next"
					onclick={() => go(1)}
					disabled={!hasNext}
					aria-label="Next image"
				>
					<span class="nav-arrow">→</span>
				</button>

			</div>

			<!-- system bar -->
			<div class="viewer-nav">
				<span class="nav-counter">{app.currentIndex + 1} / {app.total}</span>

				<div class="nav-actions">
					<button
						class="viewer-action-btn is-approve"
						onclick={approve}
					>Approve</button>
					<button
						class="viewer-action-btn is-flag"
						onclick={flag}
					>Flag</button>
				</div>

				<div class="nav-spacer"></div>

				<span class="shortcut-hint">j/k · a · f · s · m · p</span>

				<div class="mode-toggle">
					<button
						class="mode-btn"
						class:is-active={mode === 'study'}
						onclick={() => mode = 'study'}
					>Study</button><button
						class="mode-btn"
						class:is-active={mode === 'cataloging'}
						onclick={() => mode = 'cataloging'}
					>Catalog</button>
				</div>

				<button class="panel-toggle-btn" onclick={() => panelOpen = !panelOpen}>
					{panelOpen ? 'Hide' : 'Metadata'}
				</button>
			</div>
		</div>

		<!-- ── metadata panel ───────────────────────────────────────────────── -->
		{#if panelOpen}
			<div class="meta-panel">

				<!-- pinned decision bar -->
				<div class="panel-actions">
					<button class="action-approve" onclick={approve}>Approve</button>
					<button class="action-flag" onclick={flag}>Flag</button>
					<div class="actions-spacer"></div>
					<button
						class="save-btn"
						class:is-dirty={dirty}
						onclick={save}
						disabled={app.saving}
					>{app.saving ? 'Saving…' : dirty ? 'Save' : 'Saved'}</button>
				</div>

				<!-- scrollable field sections -->
				<div class="meta-scroll">

					<!-- ── Section: Description ── -->
					<div class="section section-description">
						<span class="section-head">Description</span>

						<span class="anno-label">Title</span>
						<input
							class="field-input title"
							bind:value={title}
							oninput={markDirty}
							placeholder="Untitled"
						/>

						<span class="anno-label">Description</span>
						<textarea
							class="field-textarea description"
							bind:value={description}
							oninput={markDirty}
							use:autosize
							placeholder="—"
						></textarea>
					</div>

					<!-- ── Section: Classification ── -->
					<div class="section section-classification">
						<span class="section-head">Classification</span>

						<span class="anno-label">Subjects</span>
						<input
							class="field-input field-entity"
							bind:value={subjects}
							oninput={markDirty}
							placeholder="comma-separated"
						/>
					</div>

					<!-- ── Section: Documentary ── -->
					<div class="section section-documentary">
						<span class="section-head">Documentary</span>

						<span class="anno-label">Visible text / OCR</span>
						<textarea
							class="field-textarea field-ocr"
							bind:value={visibleText}
							oninput={markDirty}
							use:autosize
							placeholder="—"
						></textarea>

						<span class="anno-label">People</span>
						<input class="field-input field-entity" bind:value={people} oninput={markDirty} placeholder="—" />

						<span class="anno-label">Places</span>
						<input class="field-input field-entity" bind:value={places} oninput={markDirty} placeholder="—" />

						<span class="anno-label">Dates</span>
						<input class="field-input field-entity" bind:value={dates} oninput={markDirty} placeholder="—" />

						<span class="anno-label">Objects</span>
						<input class="field-input field-entity" bind:value={objects} oninput={markDirty} placeholder="—" />
					</div>

					<!-- ── Section: Notes ── -->
					<div class="section section-notes">
						<span class="section-head">Notes</span>

						<span class="anno-label">Uncertainty</span>
						<textarea
							class="field-textarea"
							bind:value={uncertainty}
							oninput={markDirty}
							use:autosize
							placeholder="—"
						></textarea>

						<span class="anno-label">Reviewer notes</span>
						<textarea
							class="field-textarea"
							bind:value={reviewerNotes}
							oninput={markDirty}
							use:autosize
							placeholder="—"
						></textarea>
					</div>

					<!-- ── Section: Revision ── -->
					<div class="section section-revision">
						<details>
							<summary><span class="revise-with">Revise with</span> <span class="revise-ai">AI</span></summary>
							<select
								class="revise-preset"
								onchange={(e) => {
									const val = (e.target as HTMLSelectElement).value;
									if (val) reviseFeedback = val;
									(e.target as HTMLSelectElement).value = '';
								}}
							>
								<option value="">— quick presets —</option>
								<option value="Make this description more neutral.">Make description more neutral</option>
								<option value="Do not infer the event — describe only what is visible.">Describe only what is visible</option>
								<option value="Use simpler, public-facing language.">Simpler public-facing language</option>
								<option value="Remove any terms that are potentially offensive or outdated.">Remove offensive/outdated terms</option>
								<option value="Expand the description with more visual detail.">Expand with more visual detail</option>
								<option value="Shorten the description to two sentences.">Shorten to two sentences</option>
							</select>
							<textarea
								class="field-textarea"
								bind:value={reviseFeedback}
								placeholder="Describe what to change…"
								use:autosize
								rows="3"
							></textarea>
							<div class="revise-bar">
								<button
									class="revise-submit-btn"
									onclick={submitRevise}
									disabled={app.revising || !reviseFeedback.trim()}
								>{app.revising ? 'Revising…' : 'Send to model'}</button>
								{#if app.revising}<span class="spinner"></span>{/if}
							</div>
						</details>
					</div>

					<div class="scroll-pad"></div>
				</div>
			</div>
		{/if}
	</div>
{/if}

<style>
	/* ── empty state ── */
	.empty-state {
		height: 100%;
		display: flex;
		align-items: center;
		justify-content: center;
		font-family: var(--font-mono);
		font-size: 0.52rem;
		letter-spacing: 0.18em;
		text-transform: uppercase;
		color: var(--c-ghost);
	}

	/* ── shell ── */
	.review-shell {
		display: flex;
		height: 100vh;
		overflow: hidden;
	}

	/* ── viewer column ── */
	.viewer {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}

	/* provenance strip — top register line in royal blue, shared with panel-actions */
	.viewer-strip {
		height: var(--strip-h);
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0 1.25rem;
		border-bottom: 2px solid var(--c-accent);
		flex-shrink: 0;
	}
	.strip-col {
		font-family: var(--font-mono);
		font-size: 0.51rem;
		letter-spacing: 0.18em;
		text-transform: uppercase;
		color: var(--c-accent);
		white-space: nowrap;
	}
	.strip-sep {
		font-family: var(--font-mono);
		font-size: 0.51rem;
		color: var(--c-ghost-lt);
	}
	.strip-file {
		font-family: var(--font-mono);
		font-size: 0.52rem;
		color: var(--c-muted);
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	/* image frame with inline nav zones */
	.image-frame {
		flex: 1;
		position: relative;
		display: flex;
		align-items: center;
		justify-content: center;
		overflow: hidden;
		background: var(--c-viewer-bg);
		padding: 2.5rem;
	}
	.is-study .image-frame { padding: 3.5rem; }

	.main-img {
		max-width: 100%;
		max-height: 100%;
		object-fit: contain;
		display: block;
		box-shadow: 0 2px 12px rgba(0, 0, 0, 0.07);
	}


	/* navigation zones — large invisible hit areas */
	.nav-zone {
		position: absolute;
		top: 0;
		bottom: 0;
		width: 96px;
		background: transparent;
		border: none;
		display: flex;
		align-items: center;
		justify-content: center;
		cursor: pointer;
		opacity: 0.2;
		transition: opacity 0.2s;
		z-index: 10;
		padding: 0;
	}
	.nav-prev { left: 0; }
	.nav-next { right: 0; }
	.nav-zone:disabled { opacity: 0; cursor: default; }
	.image-frame:hover .nav-zone:not(:disabled) { opacity: 1; }

	/* royal blue arrow in white box */
	.nav-arrow {
		font-size: 1.75rem;
		color: var(--c-accent);
		font-family: var(--font-body);
		line-height: 1;
		font-weight: 300;
		pointer-events: none;
		background: var(--c-bg);
		padding: 0.3rem 0.5rem;
	}

	/* system/info bar */
	.viewer-nav {
		height: var(--nav-h);
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0 1.25rem;
		border-top: 1px solid var(--c-border-subtle);
		flex-shrink: 0;
	}

	.nav-counter {
		font-family: var(--font-mono);
		font-size: 0.55rem;
		color: var(--c-muted);
		letter-spacing: 0.08em;
		min-width: 5ch;
	}

	/* approve/flag in viewer nav (for panel-hidden state) */
	.nav-actions {
		display: flex;
		gap: 0.25rem;
		margin-left: 0.5rem;
	}
	.viewer-action-btn {
		background: transparent;
		border: 1px solid var(--c-border);
		font-family: var(--font-body);
		font-size: 0.65rem;
		font-weight: 400;
		color: var(--c-muted);
		padding: 0.2rem 0.65rem;
		cursor: pointer;
		transition: color 0.12s, border-color 0.12s, background 0.12s;
	}
	.viewer-action-btn:hover { color: var(--c-text); border-color: var(--c-muted); }
	.viewer-action-btn.is-approve:hover {
		background: var(--c-text);
		color: var(--c-bg);
		border-color: var(--c-text);
	}

	.nav-spacer { flex: 1; }

	.shortcut-hint {
		font-family: var(--font-mono);
		font-size: 0.4rem;
		letter-spacing: 0.1em;
		color: var(--c-ghost-lt);
		text-transform: uppercase;
		white-space: nowrap;
	}

	/* mode toggle */
	.mode-toggle {
		display: flex;
		border: 1px solid var(--c-border);
		margin: 0 0.5rem;
		overflow: hidden;
	}
	.mode-btn {
		background: transparent;
		border: none;
		border-left: 1px solid var(--c-border);
		font-family: var(--font-body);
		font-size: 0.6rem;
		font-weight: 400;
		color: var(--c-ghost);
		padding: 0.2rem 0.65rem;
		cursor: pointer;
		transition: background 0.12s, color 0.12s;
		white-space: nowrap;
	}
	.mode-btn:first-child { border-left: none; }
	.mode-btn:hover:not(.is-active) { color: var(--c-muted); }
	.mode-btn.is-active {
		color: var(--c-text);
		font-weight: 500;
	}

	.panel-toggle-btn {
		background: transparent;
		border: none;
		font-family: var(--font-mono);
		font-size: 0.44rem;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--c-ghost);
		padding: 0.25rem 0.25rem;
		cursor: pointer;
		transition: color 0.12s;
	}
	.panel-toggle-btn:hover { color: var(--c-text); }

	/* ── metadata panel ── */
	.meta-panel {
		display: flex;
		flex-direction: column;
		overflow: hidden;
		background: var(--c-bg);
		border-left: 2px solid var(--c-accent);
		flex-shrink: 0;
		width: 420px;
		transition: width 0.2s ease;
	}
	.is-study .meta-panel { width: 260px; }

	/* pinned decision bar — matches viewer-strip height and blue register line exactly */
	.panel-actions {
		height: var(--strip-h);
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0 1.25rem;
		border-bottom: 2px solid var(--c-accent);
		flex-shrink: 0;
	}
	.actions-spacer { flex: 1; }

	.action-approve,
	.action-flag {
		background: transparent;
		border: 1px solid var(--c-border);
		font-family: var(--font-body);
		font-size: 0.68rem;
		font-weight: 400;
		color: var(--c-muted);
		padding: 0.28rem 0.85rem;
		cursor: pointer;
		transition: color 0.12s, border-color 0.12s, background 0.12s;
	}
	.action-approve:hover {
		background: var(--c-text);
		color: var(--c-bg);
		border-color: var(--c-text);
	}
	.action-flag:hover {
		color: var(--c-text);
		border-color: var(--c-text);
	}

	.save-btn {
		background: transparent;
		border: none;
		font-family: var(--font-mono);
		font-size: 0.47rem;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--c-ghost-lt);
		padding: 0.28rem 0;
		cursor: pointer;
		transition: color 0.12s;
	}
	.save-btn.is-dirty { color: var(--c-accent); }
	.save-btn:hover:not(:disabled) { color: var(--c-text); }
	.save-btn:disabled { cursor: default; }

	/* scrollable fields — left-heavy column, editorial asymmetry */
	.meta-scroll {
		flex: 1;
		overflow-y: auto;
		padding: 0 1.25rem 0 1.875rem;
	}
	.meta-scroll::-webkit-scrollbar { width: 3px; }
	.meta-scroll::-webkit-scrollbar-thumb { background: var(--c-border); }

	/* sections — conceptual chapters with intentional spacing asymmetry */
	.section {
		padding: 2.75rem 0 0.25rem;
		border-top: 1px solid var(--c-border-subtle);
	}

	/* Description: opens the panel — no border, generous breathing */
	.section-description {
		border-top: none;
		padding-top: 2.25rem;
	}

	/* Classification: tight tab, subordinate chapter */
	.section-classification {
		padding-top: 1.25rem;
	}

	/* Documentary: archive-heavy — maximum breathing before it */
	.section-documentary {
		padding-top: 4rem;
	}

	/* Notes: generous but not as heavy as documentary */
	.section-notes {
		padding-top: 2.75rem;
	}

	/* section head — assertive chapter opener */
	.section-head {
		display: block;
		font-family: var(--font-body);
		font-size: 1.4rem;
		font-weight: 300;
		color: var(--c-text);
		letter-spacing: -0.03em;
		margin-bottom: 1.75rem;
		margin-left: -0.5rem;
	}

	/* entity/structured fields — subordinate to prose; reference voice */
	.field-entity {
		font-size: 0.82rem;
		font-weight: 400;
		color: var(--c-text-body);
	}

	/* OCR / visible text — archival density: mono, tight, small */
	.field-ocr {
		font-family: var(--font-mono);
		font-size: 0.74rem;
		font-weight: 400;
		line-height: 1.75;
		color: var(--c-muted);
	}

	/* study mode: quieter panel */
	.is-study .section-head      { font-size: 0.9rem; margin-left: -0.25rem; }
	.is-study .field-input       { font-size: 0.78rem; }
	.is-study .field-textarea    { font-size: 0.78rem; }
	.is-study .field-input.title { font-size: 1.25rem; }

	/* revision section */
	.section-revision { padding-top: 1rem; }

	.revise-with {
		font-family: var(--font-mono);
		font-size: 0.44rem;
		letter-spacing: 0.24em;
		text-transform: uppercase;
		color: var(--c-accent);
		font-weight: 400;
		vertical-align: middle;
	}
	.revise-ai {
		font-family: var(--font-mono);
		font-size: 1.5rem;
		font-weight: 500;
		color: var(--c-accent);
		letter-spacing: -0.02em;
		vertical-align: middle;
		line-height: 1;
	}

	.revise-preset {
		width: 100%;
		margin-top: 0.6rem;
		padding: 0.3rem 0.5rem;
		font-family: var(--font-body);
		font-size: 0.72rem;
		color: var(--c-muted);
		background: transparent;
		border: 1px solid var(--c-border);
		cursor: pointer;
	}

	/* generic action button (revise submit) */
	.action-btn {
		background: transparent;
		border: 1px solid var(--c-border);
		font-family: var(--font-body);
		font-size: 0.65rem;
		font-weight: 400;
		color: var(--c-muted);
		padding: 0.25rem 0.75rem;
		cursor: pointer;
		transition: color 0.12s, border-color 0.12s;
	}
	.action-btn:hover:not(:disabled) { color: var(--c-text); border-color: var(--c-muted); }
	.action-btn:disabled { opacity: 0.4; cursor: default; }

	.revise-submit-btn {
		background: var(--c-accent);
		border: none;
		font-family: var(--font-body);
		font-size: 0.72rem;
		font-weight: 500;
		letter-spacing: 0.05em;
		color: #fff;
		padding: 0.4rem 1.1rem;
		cursor: pointer;
		transition: opacity 0.12s;
	}
	.revise-submit-btn:hover:not(:disabled) { opacity: 0.85; }
	.revise-submit-btn:disabled { opacity: 0.35; cursor: default; }

	.revise-bar {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-top: 0.75rem;
		padding-bottom: 0.5rem;
	}

	.scroll-pad { height: 4rem; }
</style>
