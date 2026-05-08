"""
app/dagster/assets.py
Software-defined assets for the photo metadata pipeline.

Asset graph:
    ingested_images
        └── draft_metadata
                └── [human review happens in Streamlit — outside Dagster]
                        └── approved_metadata  (materialised on demand)
                                └── exported_json / exported_csv / exported_xmp
"""
from __future__ import annotations

from pathlib import Path

from dagster import (
    AssetIn,
    Field,
    Output,
    String,
    asset,
    get_dagster_logger,
)

from app.dagster.resources import DatabaseResource, OllamaResource


# ── 1. Ingest ─────────────────────────────────────────────────────────────────

@asset(
    group_name="ingest",
    description="Scan an image folder and register new files in the database.",
    config_schema={
        "image_folder": Field(String, description="Path to the folder of images to ingest."),
        "collection_name": Field(String, default_value="default", description="Collection name."),
    },
)
def ingested_images(
    context,
    database: DatabaseResource,
) -> Output[dict]:
    from app.db.crud import get_or_create_collection, ingest_image
    from app.utils.image_utils import find_images, sha256_file

    log = get_dagster_logger()
    cfg = context.op_config
    image_folder = cfg.get("image_folder", "")
    collection_name = cfg.get("collection_name", "default")

    if not image_folder:
        raise ValueError("image_folder must be provided in op config.")

    db = database.get_session()
    coll = get_or_create_collection(db, collection_name)
    images = find_images(image_folder)

    new_count = 0
    for img_path in images:
        file_hash = sha256_file(img_path)
        ingest_image(db, str(img_path), coll.id, file_hash)
        new_count += 1
        log.info("Ingested: %s", img_path.name)

    result = {
        "collection_name": collection_name,
        "collection_id": coll.id,
        "total_found": len(images),
        "newly_ingested": new_count,
    }
    context.add_output_metadata(result)
    return Output(result)


# ── 2. Generate draft metadata ────────────────────────────────────────────────

@asset(
    group_name="metadata_generation",
    ins={"ingest_result": AssetIn("ingested_images")},
    description="Run the local VLM over all un-drafted images and store metadata.",
)
def draft_metadata(
    context,
    database: DatabaseResource,
    ollama: OllamaResource,
    ingest_result: dict,
) -> Output[dict]:
    from app.db.crud import (
        get_collection_by_name, list_images, get_metadata,
        upsert_metadata, mark_draft_generated, snapshot_revision,
    )
    from app.models.local_vlm import generate_metadata

    log = get_dagster_logger()
    ollama.apply_to_config()
    db = database.get_session()

    collection_name = ingest_result["collection_name"]
    coll = get_collection_by_name(db, collection_name)
    if not coll:
        raise ValueError(f"Collection not found: {collection_name!r}")

    images = list_images(db, collection_id=coll.id)
    pending = [
        img for img in images
        if not (get_metadata(db, img.id) and get_metadata(db, img.id).draft_generated)
    ]

    log.info("%d images need draft generation.", len(pending))
    session_ctx = coll.session_context()

    succeeded = 0
    failed = 0
    for img in pending:
        try:
            fields = generate_metadata(img.filepath, session_ctx)
            upsert_metadata(db, img.id, fields)
            mark_draft_generated(db, img.id)
            snapshot_revision(db, img.id, "draft")
            log.info("Draft generated: %s", img.filename)
            succeeded += 1
        except Exception as e:
            log.error("Failed %s: %s", img.filename, e)
            failed += 1

    result = {
        "collection_name": collection_name,
        "collection_id": coll.id,
        "processed": succeeded,
        "failed": failed,
    }
    context.add_output_metadata(result)
    return Output(result)


# ── 3. Approved metadata (materialised on demand after human review) ──────────

@asset(
    group_name="review",
    description="Snapshot of all approved records — materialise this after a review session.",
    config_schema={
        "collection_name": Field(String, default_value="", description="Filter to a specific collection (empty = all)."),
    },
)
def approved_metadata(
    context,
    database: DatabaseResource,
) -> Output[list[dict]]:
    from app.db.crud import get_approved_records, get_collection_by_name

    collection_name = context.op_config.get("collection_name", "")
    db = database.get_session()
    col_id = None
    if collection_name:
        coll = get_collection_by_name(db, collection_name)
        col_id = coll.id if coll else None

    records = get_approved_records(db, collection_id=col_id)
    data = []
    for image, rec in records:
        entry = rec.to_dict()
        entry["filename"] = image.filename
        entry["filepath"] = image.filepath
        for key in ("subjects", "people", "places", "objects"):
            entry[key] = rec.get_tags(key)
        data.append(entry)

    context.add_output_metadata({
        "approved_count": len(data),
        "collection": collection_name or "all",
    })
    return Output(data)


# ── 4. Export assets ──────────────────────────────────────────────────────────

@asset(
    group_name="export",
    ins={"records": AssetIn("approved_metadata")},
    description="Export approved metadata to JSON.",
    config_schema={
        "output_path": Field(String, default_value="", description="Override output path."),
    },
)
def exported_json(
    context,
    records: list[dict],
) -> Output[str]:
    from app.config import EXPORTS_DIR
    import json as _json

    output_path = Path(context.op_config.get("output_path") or str(EXPORTS_DIR / "approved_metadata.json"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        _json.dump(records, f, indent=2, ensure_ascii=False, default=str)

    context.add_output_metadata({"path": str(output_path), "record_count": len(records)})
    return Output(str(output_path))


@asset(
    group_name="export",
    ins={"records": AssetIn("approved_metadata")},
    description="Export approved metadata to CSV.",
    config_schema={
        "output_path": Field(String, default_value="", description="Override output path."),
    },
)
def exported_csv(
    context,
    records: list[dict],
) -> Output[str]:
    import csv
    from app.config import EXPORTS_DIR

    output_path = Path(context.op_config.get("output_path") or str(EXPORTS_DIR / "approved_metadata.csv"))
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not records:
        output_path.write_text("(no approved records)\n")
        context.add_output_metadata({"path": str(output_path), "record_count": 0})
        return Output(str(output_path))

    flat = []
    for r in records:
        row = dict(r)
        for key in ("subjects", "people", "places", "objects"):
            val = row.get(key, [])
            row[key] = " | ".join(val) if isinstance(val, list) else val
        flat.append(row)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(flat[0].keys()))
        writer.writeheader()
        writer.writerows(flat)

    context.add_output_metadata({"path": str(output_path), "record_count": len(flat)})
    return Output(str(output_path))


@asset(
    group_name="export",
    ins={"records": AssetIn("approved_metadata")},
    description="Write XMP sidecar files via ExifTool.",
    config_schema={
        "output_dir": Field(String, default_value="", description="Override output directory."),
        "collection_name": Field(String, default_value="", description="Filter to a specific collection."),
    },
)
def exported_xmp(
    context,
    database: DatabaseResource,
    records: list[dict],
) -> Output[str]:
    from app.db.crud import get_approved_records, get_collection_by_name
    from app.export import export_xmp
    from app.config import EXPORTS_DIR

    cfg = context.op_config
    collection_name = cfg.get("collection_name", "")
    db = database.get_session()
    col_id = None
    if collection_name:
        coll = get_collection_by_name(db, collection_name)
        col_id = coll.id if coll else None

    orm_records = get_approved_records(db, collection_id=col_id)
    out_dir = Path(cfg.get("output_dir") or str(EXPORTS_DIR / "xmp_sidecars"))

    written = export_xmp(orm_records, out_dir)
    context.add_output_metadata({
        "output_dir": str(out_dir),
        "files_written": len(written),
    })
    return Output(str(out_dir))
