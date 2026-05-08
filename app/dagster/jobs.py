"""
app/dagster/jobs.py
Pre-wired job definitions.

  ingest_and_generate_job  — ingest a folder + generate all drafts
  export_job               — export approved records (run after review)

Trigger either manually in the Dagster UI, via CLI, or attach a
schedule/sensor in definitions.py when the trigger pattern is known.
"""
from dagster import define_asset_job, AssetSelection

# Runs ingest → draft metadata
ingest_and_generate_job = define_asset_job(
    name="ingest_and_generate",
    selection=AssetSelection.assets("ingested_images", "draft_metadata"),
    description="Ingest a folder of images and generate draft metadata via Ollama.",
)

# Materialises approved_metadata snapshot → all three export formats
export_all_job = define_asset_job(
    name="export_all",
    selection=AssetSelection.assets(
        "approved_metadata",
        "exported_json",
        "exported_csv",
        "exported_xmp",
    ),
    description="Export all approved metadata to JSON, CSV, and XMP sidecars.",
)

# Export to JSON only (lighter weight)
export_json_job = define_asset_job(
    name="export_json",
    selection=AssetSelection.assets("approved_metadata", "exported_json"),
)
