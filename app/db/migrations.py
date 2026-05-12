"""
app/db/migrations.py
Lightweight migration helpers — no Alembic required for an MVP.
Run via: python -m app.cli db-check
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect, text

from app.db.schema import Base, get_engine


def check_and_migrate(verbose: bool = True) -> list[str]:
    """
    Inspect the live DB, add missing tables/columns, and run data migrations.
    Returns a list of actions taken.
    """
    engine = get_engine()
    inspector = inspect(engine)
    actions: list[str] = []

    # Phase 1: create missing tables and add missing columns
    for table in Base.metadata.sorted_tables:
        table_name = table.name
        if not inspector.has_table(table_name):
            if verbose:
                print(f"  ✚ Creating missing table: {table_name}")
            table.create(engine)
            actions.append(f"created_table:{table_name}")
            continue

        existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
        for col in table.columns:
            if col.name not in existing_cols:
                col_type = col.type.compile(engine.dialect)
                nullable = "" if col.nullable else " NOT NULL"
                default = ""
                if col.default is not None and col.default.is_scalar:
                    val = col.default.arg
                    if isinstance(val, str):
                        val = f"'{val}'"
                    default = f" DEFAULT {val}"
                stmt = (
                    f"ALTER TABLE {table_name} ADD COLUMN "
                    f"{col.name} {col_type}{default}{nullable}"
                )
                with engine.connect() as conn:
                    conn.execute(text(stmt))
                    conn.commit()
                msg = f"added_column:{table_name}.{col.name}"
                actions.append(msg)
                if verbose:
                    print(f"  ✚ {msg}")

    # Phase 2: wrap legacy image rows that have no item_id into Item records
    with engine.connect() as conn:
        # images table must exist before we query it
        if inspector.has_table("images"):
            result = conn.execute(
                text("SELECT COUNT(*) FROM images WHERE item_id IS NULL")
            ).scalar()
            if result and result > 0:
                if verbose:
                    print(f"  ✚ Migrating {result} legacy image(s) to item records…")
                _migrate_images_to_items(conn, verbose)
                actions.append(f"migrated_legacy_images:{result}")

    # Phase 3: rename legacy status values
    status_renames = {
        "needs_review": "queue",
        "in_progress":  "working",
        "revised":      "working",
        "approved":     "ready",
        "flagged":      "hold",
    }
    with engine.connect() as conn:
        if inspector.has_table("metadata_records"):
            for old, new in status_renames.items():
                result = conn.execute(
                    text("UPDATE metadata_records SET review_status = :new WHERE review_status = :old"),
                    {"old": old, "new": new},
                ).rowcount
                if result:
                    msg = f"renamed_status:{old}→{new} ({result} rows)"
                    actions.append(msg)
                    if verbose:
                        print(f"  ✚ {msg}")
            conn.commit()

    if not actions and verbose:
        print("  ✔ Schema is up to date — no changes needed.")

    return actions


def _migrate_images_to_items(conn, verbose: bool) -> None:
    """Create one Item per legacy Image and rewire metadata_records / revision_history."""
    images = conn.execute(
        text("SELECT id, collection_id, filename, filepath FROM images WHERE item_id IS NULL ORDER BY id")
    ).fetchall()

    for img_id, coll_id, filename, filepath in images:
        item_key = Path(filepath).stem if filepath else str(img_id)

        conn.execute(
            text(
                "INSERT INTO items (collection_id, series, item_key, folder_path, created_at) "
                "VALUES (:coll_id, '', :item_key, NULL, datetime('now'))"
            ),
            {"coll_id": coll_id, "item_key": item_key},
        )
        item_id = conn.execute(text("SELECT last_insert_rowid()")).scalar()

        conn.execute(
            text("UPDATE images SET item_id = :item_id, page_number = 1 WHERE id = :img_id"),
            {"item_id": item_id, "img_id": img_id},
        )

        # metadata_records still has the legacy image_id column — update by that
        conn.execute(
            text("UPDATE metadata_records SET item_id = :item_id WHERE image_id = :img_id"),
            {"item_id": item_id, "img_id": img_id},
        )

        # revision_history same
        conn.execute(
            text("UPDATE revision_history SET item_id = :item_id WHERE image_id = :img_id"),
            {"item_id": item_id, "img_id": img_id},
        )

        if verbose:
            print(f"    → image {img_id} ({filename}) → item {item_id}")

    conn.commit()
