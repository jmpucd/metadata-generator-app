# Metadata Generator App — Process Map

Reference for developers integrating this pipeline into Dagster and CAS.

---

## Overview

```
[Image files on disk]
        │
        ▼
 1. INGEST (CLI)          → SQLite: items, images, metadata_records (status=queue)
        │
        ▼
 2. GENERATE (CLI/Dagster) → VLM processes each image → draft metadata stored
        │
        ▼
 3. REVIEW (Web UI)        → Human edits + optional VLM revise loop → status=ready
        │
        ▼
 4. EXPORT (CLI/Dagster)   → JSON / CSV / XMP written to data/exports/
```

Human review (step 3) is interactive and cannot be automated.
Steps 1, 2, and 4 are fully scriptable — see `run_pipeline.sh`.

---

## Processes

### 1. Ingest

**Purpose:** Registers image files in the database so they can be processed.

**Command:**
```bash
python -m app.cli ingest <images_dir> --collection "Collection Name"
```

**What it does:**
- Recursively finds `.jpg .jpeg .png .tif .tiff .gif .bmp .webp` files
- SHA256-hashes each file for deduplication
- Creates one `Item` per image (or per subfolder for multi-page items)
- Creates one `Image` row per physical file
- Creates one `MetadataRecord` per item (`review_status="queue"`, `draft_generated=False`)

**Input:** Directory of image files  
**Output:** Rows in `data/metadata/review.db` (tables: `items`, `images`, `metadata_records`)  
**Dagster asset:** `ingested_images` (`app/dagster/assets.py`)  
**Key code:** `app/cli.py → ingest()`, `app/utils/image_utils.py → find_images()`

---

### 2. Generate (VLM / AI step)

**Purpose:** Sends each un-drafted image to a Vision-Language Model and stores the resulting metadata as a draft.

**Command:**
```bash
python -m app.cli generate --collection "Collection Name"
```

**What it does:**
- Fetches all items where `draft_generated=False`
- Loads the first (representative) image page per item
- Resizes image to 2048px max, JPEG 85%, base64-encodes
- Sends image + structured prompt to VLM backend
- Parses JSON response into metadata fields
- Updates `metadata_records` (`draft_generated=True`, `review_status="queue"`)
- Appends a snapshot to `revision_history` (`revision_type="draft"`)

**VLM backends** (set `MODEL_BACKEND` in `.env`):

| Value | Where | Model | Auth |
|-------|-------|-------|------|
| `ollama` (default) | `https://samwise.library.ucdavis.edu/ollama` | `qwen2.5vl:32b` | `OLLAMA_TOKEN` env var |
| `qwen_vl` | Local (HuggingFace Transformers) | `Qwen/Qwen2-VL-7B-Instruct` | none |
| `mock` | In-process stub | — | none (testing only) |

**Metadata fields produced:**
`title`, `description`, `visible_text`, `subjects[]`, `people[]`, `places[]`, `dates`, `objects[]`, `uncertainty_notes`, `reviewer_notes`

**Input:** Images in DB with `draft_generated=False`  
**Output:** Populated `metadata_records` rows  
**Dagster asset:** `draft_metadata` (depends on `ingested_images`)  
**Key code:** `app/models/local_vlm.py → generate_metadata(image_path, session_context)`

---

### 3. API Server (FastAPI)

**Purpose:** REST backend serving the review UI and handling VLM revision calls during human review.

**Command:**
```bash
uvicorn api.main:app --port 8000 --reload
```

**Port:** 8000  
**Entry point:** `api/main.py`

**Key routes:**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/collections` | List collections |
| POST | `/api/collections` | Create collection |
| GET | `/api/collections/{id}/items` | List items (pageable, filter by status) |
| GET | `/api/images/{id}/file` | Serve original image |
| GET | `/api/images/{id}/thumbnail` | Serve 900px JPEG thumbnail |
| GET | `/api/metadata/{item_id}` | Read metadata record |
| PUT | `/api/metadata/{item_id}` | Update metadata fields |
| PATCH | `/api/metadata/{item_id}/status` | Change review status |
| POST | `/api/metadata/{item_id}/revise` | VLM re-run with reviewer feedback |
| GET | `/api/collections/{id}/export` | Trigger export (`?format=json\|csv`) |
| GET | `/api/health` | Health check |
| GET | `/api/config` | Active model backend config |

**On startup:** Runs `db-check` (schema migration) automatically.

---

### 4. Frontend (SvelteKit)

**Purpose:** Web UI for human metadata review.

**Dev command:**
```bash
cd ui && npm run dev    # port 5173
```

**Production build:**
```bash
cd ui && npm run build  # outputs to ui/build/
# FastAPI then serves ui/build/ as static files — no separate Node process needed
```

**Routes:**
- `/review` — main review interface (image + metadata side-by-side)
- `/grid` — thumbnail grid view
- `/setup` — collection context configuration
- `/export` — export controls and status counts

**Proxy:** All `/api/*` calls are forwarded to `http://127.0.0.1:8000` (configured in `ui/vite.config.ts`).

---

### 5. Revise (VLM re-run with feedback)

**Purpose:** Lets reviewers give text feedback to the VLM and get an updated draft without leaving the UI.

**How it's triggered:** Reviewer types feedback in the UI → clicks Revise → fires `POST /api/metadata/{item_id}/revise`

**What it does:**
- Takes current metadata + reviewer's feedback text
- Sends image + current metadata + feedback to VLM
- Stores revised metadata in `metadata_records`
- Appends snapshot to `revision_history` (`revision_type="model_revision"`)

**Key code:** `app/models/local_vlm.py → revise_metadata(image_path, current_metadata, feedback, session_context)`  
**Route:** `api/routes/revise.py`

---

### 6. Export

**Purpose:** Writes approved metadata to output files for downstream ingest (ContentDM, DSpace, XMP sidecars, etc.).

**Command:**
```bash
python -m app.cli export --format json    # or csv, xmp
```

**What it does:**
- Fetches all items with `review_status IN ('ready', 'exported')`
- Writes output file(s) to `data/exports/`
- Updates all exported items to `review_status="exported"`

**Output formats:**

| Format | Output path | Notes |
|--------|-------------|-------|
| `json` | `data/exports/approved_metadata.json` | Array of objects |
| `csv` | `data/exports/approved_metadata.csv` | List fields pipe-separated |
| `xmp` | `data/exports/xmp_sidecars/*.xmp` | Requires `exiftool` on PATH |

**Dagster assets:** `approved_metadata` → `exported_json` / `exported_csv` / `exported_xmp`  
**Dagster jobs:** `export_all_job`, `export_json_job` (`app/dagster/jobs.py`)  
**Key code:** `app/export/__init__.py`

---

### 7. Dagster (orchestration layer)

**Purpose:** Software-defined asset graph for running and monitoring the automated pipeline steps. Already wired — sensors/schedules are stubbed out and ready to activate.

**Launch UI:**
```bash
python -m app.cli dagster-dev    # → http://localhost:3000
```

**Run a job directly (no UI):**
```bash
python -m app.cli dagster-run --job ingest_and_generate --image-folder /path/to/images --collection "Name"
python -m app.cli dagster-run --job export_all
python -m app.cli dagster-run --job export_json
```

**Asset graph:**
```
ingested_images
      ↓
draft_metadata
      ↓
  [human review — outside Dagster]
      ↓
approved_metadata
      ↓
exported_json   exported_csv   exported_xmp
```

**Pre-wired jobs:**

| Job | Assets run |
|-----|------------|
| `ingest_and_generate_job` | `ingested_images` + `draft_metadata` |
| `export_all_job` | `approved_metadata` + all 3 export assets |
| `export_json_job` | `approved_metadata` + `exported_json` |

**Resources:** `DatabaseResource` (SQLite/Postgres), `OllamaResource` (remote Ollama config)  
**Entry point:** `app/dagster/definitions.py`

---

## Database

**Location:** `data/metadata/review.db` (SQLite; override with `DATABASE_URL` env var for Postgres)

**Tables:**

| Table | Purpose |
|-------|---------|
| `collections` | One per batch/collection; stores VLM context (style, vocab, date range, people, rules) |
| `items` | One logical archival item per single image or multi-page folder |
| `images` | One physical file per row; items have one or more pages |
| `metadata_records` | Current metadata for each item; one active record per item |
| `revision_history` | Append-only audit log of every metadata snapshot + feedback |

**Review status lifecycle:**
```
queue → working → ready → exported
               ↘ hold ↗
```

---

## Configuration

All settings live in `app/config.py` and can be overridden via `.env`.

| Variable | Default | Purpose |
|----------|---------|---------|
| `MODEL_BACKEND` | `ollama` | Which VLM to use (`ollama`, `qwen_vl`, `mock`) |
| `OLLAMA_BASE_URL` | `https://samwise.library.ucdavis.edu/ollama` | Remote Ollama endpoint |
| `OLLAMA_MODEL` | `qwen2.5vl:32b` | Ollama model name |
| `OLLAMA_TOKEN` | — | Bearer auth token for Ollama |
| `ANTHROPIC_API_KEY` | — | Claude API key (if using Claude backend) |
| `IMAGES_DIR` | `images/incoming` | Default source folder |
| `DATABASE_URL` | SQLite at `data/metadata/review.db` | Override for Postgres |

Copy `.env.example` to `.env` before first run.

---

## Startup (dev)

Two terminals:

```bash
# Terminal 1 — API
source .venv/bin/activate
uvicorn api.main:app --port 8000 --reload

# Terminal 2 — UI
cd ui && npm run dev
```

SSH tunnel from local machine:
```bash
ssh -L 5173:localhost:5173 -L 8000:localhost:8000 digitization
```

Then open `http://localhost:5173`.

---

## One-shot pipeline script

See `run_pipeline.sh` for a single script that runs ingest → generate → export.

```bash
./run_pipeline.sh images/incoming "Collection Name" json
```
