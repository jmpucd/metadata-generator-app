"""
app/dagster/definitions.py
Top-level Dagster Definitions object.
Point DAGSTER_HOME and DAGSTER_MODULE_NAME at this, or run:

    dagster dev -m app.dagster.definitions
"""
from dagster import Definitions, EnvVar

from app.dagster.assets import (
    ingested_images,
    draft_metadata,
    approved_metadata,
    exported_json,
    exported_csv,
    exported_xmp,
)
from app.dagster.jobs import ingest_and_generate_job, export_all_job, export_json_job
from app.dagster.resources import DatabaseResource, OllamaResource

# ── Resource configs ───────────────────────────────────────────────────────────
# Override any of these via environment variables or Dagster's UI config.

resources = {
    "ollama": OllamaResource(
        base_url="https://samwise.library.ucdavis.edu/ollama",
        model="qwen2.5vl:32b",
        token=EnvVar("OLLAMA_TOKEN"),
    ),
    "database": DatabaseResource(
        # Leave empty to use the default SQLite path from app.config.
        # For production on CentOS, set DATABASE_URL to a Postgres URL:
        #   postgresql+psycopg2://user:pass@host/dbname
        database_url="",  # uses default SQLite from app.config; set DATABASE_URL env var to override
    ),
}

defs = Definitions(
    assets=[
        ingested_images,
        draft_metadata,
        approved_metadata,
        exported_json,
        exported_csv,
        exported_xmp,
    ],
    jobs=[
        ingest_and_generate_job,
        export_all_job,
        export_json_job,
    ],
    resources=resources,
    # ── Attach a schedule or sensor here when the trigger pattern is decided ──
    # schedules=[nightly_ingest_schedule],
    # sensors=[new_image_sensor],
)
