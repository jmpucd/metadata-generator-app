"""
app/db/crud.py — all database read/write operations.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.db.schema import Collection, Item, Image, MetadataRecord, RevisionHistory


# ── Collections ───────────────────────────────────────────────────────────────

def get_or_create_collection(db: Session, name: str, **kwargs) -> Collection:
    coll = db.query(Collection).filter_by(name=name).first()
    if coll is None:
        coll = Collection(name=name, **kwargs)
        db.add(coll)
        db.commit()
        db.refresh(coll)
    return coll


def update_collection(db: Session, collection_id: int, **kwargs) -> Collection:
    coll = db.get(Collection, collection_id)
    for k, v in kwargs.items():
        setattr(coll, k, v)
    db.commit()
    db.refresh(coll)
    return coll


def list_collections(db: Session) -> list[Collection]:
    return db.query(Collection).order_by(Collection.created_at.desc()).all()


def get_collection_by_name(db: Session, name: str) -> Optional[Collection]:
    return db.query(Collection).filter_by(name=name).first()


# ── Items ─────────────────────────────────────────────────────────────────────

def ingest_item(
    db: Session,
    collection_id: int,
    item_key: str,
    pages: list[tuple[str, int]],  # [(filepath, page_number), ...]
    series: str = "",
    folder_path: Optional[str] = None,
) -> Item:
    """Create an Item and its pages. Idempotent: skips if first page already ingested."""
    if pages:
        existing = db.query(Image).filter_by(filepath=pages[0][0]).first()
        if existing and existing.item_id:
            return db.get(Item, existing.item_id)

    item = Item(
        collection_id=collection_id,
        series=series,
        item_key=item_key,
        folder_path=folder_path,
    )
    db.add(item)
    db.flush()

    for filepath, page_num in pages:
        existing = db.query(Image).filter_by(filepath=filepath).first()
        if existing:
            existing.item_id = item.id
            existing.page_number = page_num
        else:
            db.add(Image(
                collection_id=collection_id,
                item_id=item.id,
                page_number=page_num,
                filename=Path(filepath).name,
                filepath=filepath,
            ))

    db.add(MetadataRecord(item_id=item.id, review_status="queue"))
    db.commit()
    db.refresh(item)
    return item


def list_items(
    db: Session,
    collection_id: Optional[int] = None,
    status: Optional[str] = None,
) -> list[Item]:
    q = db.query(Item)
    if collection_id:
        q = q.filter(Item.collection_id == collection_id)
    if status:
        q = q.join(MetadataRecord).filter(MetadataRecord.review_status == status)
    return q.order_by(Item.created_at).all()


def get_item(db: Session, item_id: int) -> Optional[Item]:
    return db.get(Item, item_id)


# ── Images (file serving only) ────────────────────────────────────────────────

def get_image(db: Session, image_id: int) -> Optional[Image]:
    return db.get(Image, image_id)


# ── Metadata records ──────────────────────────────────────────────────────────

def get_metadata(db: Session, item_id: int) -> Optional[MetadataRecord]:
    return db.query(MetadataRecord).filter_by(item_id=item_id).first()


def upsert_metadata(db: Session, item_id: int, fields: dict) -> MetadataRecord:
    rec = get_metadata(db, item_id)
    if rec is None:
        rec = MetadataRecord(item_id=item_id)
        db.add(rec)

    tag_fields = {"subjects", "people", "places", "objects"}
    skip_fields = {"id", "item_id", "image_id", "review_status", "draft_generated",
                   "last_revised_at", "approved_at", "approved_by"}

    for key, value in fields.items():
        if key in skip_fields:
            continue
        if key in tag_fields:
            if isinstance(value, list):
                value = json.dumps(value)
            setattr(rec, key, value)
        elif hasattr(rec, key):
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value) if value else ""
            setattr(rec, key, value)

    rec.last_revised_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(rec)
    return rec


def set_review_status(db: Session, item_id: int, status: str) -> MetadataRecord:
    rec = get_metadata(db, item_id)
    rec.review_status = status
    if status == "ready":
        rec.approved_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(rec)
    return rec


def mark_draft_generated(db: Session, item_id: int) -> None:
    rec = get_metadata(db, item_id)
    rec.draft_generated = True
    rec.review_status = "queue"
    db.commit()


# ── Revision history ──────────────────────────────────────────────────────────

def snapshot_revision(
    db: Session,
    item_id: int,
    revision_type: str,
    feedback: Optional[str] = None,
    revised_by: str = "system",
) -> RevisionHistory:
    rec = get_metadata(db, item_id)
    snap = rec.to_dict() if rec else {}
    entry = RevisionHistory(
        item_id=item_id,
        revision_type=revision_type,
        metadata_snapshot=json.dumps(snap),
        feedback_given=feedback,
        revised_by=revised_by,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_revision_history(db: Session, item_id: int) -> list[RevisionHistory]:
    return (
        db.query(RevisionHistory)
        .filter_by(item_id=item_id)
        .order_by(RevisionHistory.revised_at.desc())
        .all()
    )


# ── Export helpers ────────────────────────────────────────────────────────────

def get_approved_records(db: Session, collection_id: Optional[int] = None):
    """Return (Item, MetadataRecord) pairs for all approved items."""
    q = db.query(Item, MetadataRecord).join(MetadataRecord)
    q = q.filter(MetadataRecord.review_status.in_(["ready", "exported"]))
    if collection_id:
        q = q.filter(Item.collection_id == collection_id)
    return q.all()


# ── Stats ─────────────────────────────────────────────────────────────────────

def status_counts(db: Session, collection_id: Optional[int] = None) -> dict:
    from sqlalchemy import func
    q = db.query(MetadataRecord.review_status, func.count()).join(Item)
    if collection_id:
        q = q.filter(Item.collection_id == collection_id)
    rows = q.group_by(MetadataRecord.review_status).all()
    return {status: count for status, count in rows}
