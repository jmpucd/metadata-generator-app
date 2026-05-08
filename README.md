# Photo Metadata Review App

A local-first web app for reviewing and refining AI-generated metadata for library photo collections.
All images and metadata stay on your machine. No image data is sent to commercial APIs.

---

## Architecture Overview

```
photo_review_app/
├── app/
│   ├── __init__.py
│   ├── cli.py                  # Typer CLI entry point
│   ├── config.py               # App-wide settings / constants
│   ├── db/
│   │   ├── __init__.py
│   │   ├── schema.py           # SQLAlchemy models
│   │   ├── crud.py             # DB read/write helpers
│   │   └── migrations.py       # Simple schema migration helpers
│   ├── models/
│   │   ├── __init__.py
│   │   └── local_vlm.py        # Local VLM backend (Qwen-VL or swap)
│   ├── export/
│   │   ├── __init__.py
│   │   ├── json_export.py
│   │   ├── csv_export.py
│   │   └── xmp_export.py       # ExifTool-based XMP/IPTC sidecar
│   ├── utils/
│   │   ├── __init__.py
│   │   └── image_utils.py      # Thumbnail generation, path helpers
│   └── pages/                  # Streamlit multi-page app
│       ├── 1_Review.py
│       ├── 2_Session_Setup.py
│       └── 3_Export.py
├── streamlit_app.py            # Main Streamlit entry point
├── data/
│   ├── images/                 # Symlink or copy your image folders here
│   ├── metadata/               # review.db lives here
│   └── exports/                # JSON/CSV/XMP output
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## Data Flow

```
[Local Images] → CLI ingest → SQLite DB (image records)
                                   ↓
                         CLI generate (Qwen-VL) → draft metadata in DB
                                   ↓
                         Streamlit Review UI → human edits + feedback
                                   ↓
                         Local VLM revision pass → revised metadata
                                   ↓
                         Approve → CLI export (JSON / CSV / XMP sidecar)
```

---

## Dagster Pipeline

The pipeline is defined as software-defined assets in `app/dagster/`.

```
ingested_images → draft_metadata → [Streamlit review] → approved_metadata → exported_*
```

```bash
# Launch Dagster UI
python -m app.cli dagster-dev
# Then open http://localhost:3000

# Or run a job directly from CLI
python -m app.cli dagster-run --job ingest_and_generate \
    --image-folder /path/to/images --collection "Farm Life 1940s"

python -m app.cli dagster-run --job export_all
```

**Asset groups:**
- `ingest` — `ingested_images`
- `metadata_generation` — `draft_metadata`
- `review` — `approved_metadata` (materialise after a Streamlit review session)
- `export` — `exported_json`, `exported_csv`, `exported_xmp`

**Triggers:** Schedule and sensor stubs are in `app/dagster/triggers.py` — uncomment and import into `definitions.py` when the trigger pattern is decided.

**Postgres:** When moving to CentOS, set `DATABASE_URL=postgresql+psycopg2://user:pass@host/dbname` — no other code changes needed.

---

## Quickstart

```bash
# Install dependencies
pip install -r requirements.txt

# Ingest a folder of images
python -m app.cli ingest /path/to/images --collection "Farm Life 1940s"

# Generate draft metadata (requires local Qwen-VL)
python -m app.cli generate --collection "Farm Life 1940s"

# Launch the review UI
python -m app.cli review

# Export approved records
python -m app.cli export --format json
python -m app.cli export --format csv
python -m app.cli export --format xmp
```

---

## Swapping the Local Model

The VLM backend is isolated in `app/models/local_vlm.py`.
To swap Qwen-VL for another model (LLaVA, Moondream, Ollama, etc.),
implement the same interface:

```python
def generate_metadata(image_path: str, session_context: dict) -> dict
def revise_metadata(image_path: str, current_metadata: dict, feedback: str, session_context: dict) -> dict
```

---

## Review Statuses

| Status | Meaning |
|---|---|
| `needs_review` | Draft metadata generated, not yet reviewed |
| `in_progress` | Reviewer has opened/edited but not finalised |
| `revised` | Sent back to local model for a revision pass |
| `approved` | Reviewer signed off — eligible for export |
| `flagged` | Needs human attention (sensitive content, uncertainty, etc.) |
