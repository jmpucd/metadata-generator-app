"""
app/db/crud.py — all database read/write operations.
Keep business logic out of here; this is a thin data-access layer.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.db.schema import Collection, Image, MetadataRecord, RevisionHistory


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


# ── Images ────────────────────────────────────────────────────────────────────

def ingest_image(db: Session, filepath: str, collection_id: int, file_hash: str = "") -> Image:
    """Add an image record if it doesn't already exist (idempotent by filepath)."""
    existing = db.query(Image).filter_by(filepath=filepath).first()
    if existing:
        return existing
    img = Image(
        collection_id=collection_id,
        filename=Path(filepath).name,
        filepath=filepath,
        file_hash=file_hash,
    )
    db.add(img)
    db.commit()
    db.refresh(img)
    # Create an empty metadata record immediately
    rec = MetadataRecord(image_id=img.id, review_status="needs_review")
    db.add(rec)
    db.commit()
    return img


def list_images(
    db: Session,
    collection_id: Optional[int] = None,
    status: Optional[str] = None,
) -> list[Image]:
    q = db.query(Image)
    if collection_id:
        q = q.filter(Image.collection_id == collection_id)
    if status:
        q = q.join(MetadataRecord).filter(MetadataRecord.review_status == status)
    return q.order_by(Image.ingested_at).all()


def get_image(db: Session, image_id: int) -> Optional[Image]:
    return db.get(Image, image_id)


# ── Metadata records ──────────────────────────────────────────────────────────

def get_metadata(db: Session, image_id: int) -> Optional[MetadataRecord]:
    return db.query(MetadataRecord).filter_by(image_id=image_id).first()


def upsert_metadata(db: Session, image_id: int, fields: dict) -> MetadataRecord:
    """Write metadata fields to the DB and snapshot to history."""
    rec = get_metadata(db, image_id)
    if rec is None:
        rec = MetadataRecord(image_id=image_id)
        db.add(rec)

    tag_fields = {"subjects", "people", "places", "objects"}
    for key, value in fields.items():
        if key in tag_fields:
            if isinstance(value, list):
                value = json.dumps(value)
            setattr(rec, key, value)
        elif hasattr(rec, key):
            setattr(rec, key, value)

    rec.last_revised_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(rec)
    return rec


def set_review_status(db: Session, image_id: int, status: str) -> MetadataRecord:
    rec = get_metadata(db, image_id)
    rec.review_status = status
    if status == "approved":
        rec.approved_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(rec)
    return rec


def mark_draft_generated(db: Session, image_id: int) -> None:
    rec = get_metadata(db, image_id)
    rec.draft_generated = True
    rec.review_status = "needs_review"
    db.commit()


# ── Revision history ──────────────────────────────────────────────────────────

def snapshot_revision(
    db: Session,
    image_id: int,
    revision_type: str,
    feedback: Optional[str] = None,
    revised_by: str = "system",
) -> RevisionHistory:
    rec = get_metadata(db, image_id)
    snap = rec.to_dict() if rec else {}
    entry = RevisionHistory(
        image_id=image_id,
        revision_type=revision_type,
        metadata_snapshot=json.dumps(snap),
        feedback_given=feedback,
        revised_by=revised_by,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_revision_history(db: Session, image_id: int) -> list[RevisionHistory]:
    return (
        db.query(RevisionHistory)
        .filter_by(image_id=image_id)
        .order_by(RevisionHistory.revised_at.desc())
        .all()
    )


# ── Export helpers ────────────────────────────────────────────────────────────

def get_approved_records(db: Session, collection_id: Optional[int] = None):
    """Return (Image, MetadataRecord) pairs for all approved images."""
    q = db.query(Image, MetadataRecord).join(MetadataRecord)
    q = q.filter(MetadataRecord.review_status == "approved")
    if collection_id:
        q = q.filter(Image.collection_id == collection_id)
    return q.all()


# ── Stats ─────────────────────────────────────────────────────────────────────

def status_counts(db: Session, collection_id: Optional[int] = None) -> dict:
    from sqlalchemy import func
    q = db.query(MetadataRecord.review_status, func.count()).join(Image)
    if collection_id:
        q = q.filter(Image.collection_id == collection_id)
    rows = q.group_by(MetadataRecord.review_status).all()
    return {status: count for status, count in rows}
