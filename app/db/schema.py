"""
app/db/schema.py — SQLAlchemy ORM models.

Tables
------
collections     One row per review session / collection.
items           One logical item — single image or multi-page folder.
images          One row per physical image file (a page of an item).
metadata_records  Current metadata for an item (one active row per item).
revision_history  Append-only log of every metadata snapshot + feedback.
"""
from __future__ import annotations

import datetime
import json
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session

from app.config import DATABASE_URL


class Base(DeclarativeBase):
    pass


# ── Collections ────────────────────────────────────────────────────────────────

class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description_style: Mapped[Optional[str]] = mapped_column(Text)
    controlled_vocabulary: Mapped[Optional[str]] = mapped_column(Text)
    known_locations: Mapped[Optional[str]] = mapped_column(Text)
    known_date_range: Mapped[Optional[str]] = mapped_column(String(100))
    known_people_orgs: Mapped[Optional[str]] = mapped_column(Text)
    terms_to_avoid: Mapped[Optional[str]] = mapped_column(Text)
    institutional_rules: Mapped[Optional[str]] = mapped_column(Text)
    rights_sensitivity_notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    items: Mapped[list["Item"]] = relationship("Item", back_populates="collection")

    def session_context(self) -> dict:
        return {
            "collection_name": self.name,
            "description_style": self.description_style or "",
            "controlled_vocabulary": self.controlled_vocabulary or "",
            "known_locations": self.known_locations or "",
            "known_date_range": self.known_date_range or "",
            "known_people_orgs": self.known_people_orgs or "",
            "terms_to_avoid": self.terms_to_avoid or "",
            "institutional_rules": self.institutional_rules or "",
            "rights_sensitivity_notes": self.rights_sensitivity_notes or "",
        }


# ── Items (logical archival items; one item = one metadata record) ─────────────

class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey("collections.id"), nullable=False)
    series: Mapped[Optional[str]] = mapped_column(String(500))    # parent folder name
    item_key: Mapped[str] = mapped_column(String(500), nullable=False)  # folder/filename stem
    folder_path: Mapped[Optional[str]] = mapped_column(String(1000))    # None for single-image items
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    collection: Mapped["Collection"] = relationship("Collection", back_populates="items")
    pages: Mapped[list["Image"]] = relationship(
        "Image", back_populates="item", order_by="Image.page_number"
    )
    metadata_record: Mapped[Optional["MetadataRecord"]] = relationship(
        "MetadataRecord", back_populates="item", uselist=False
    )
    history: Mapped[list["RevisionHistory"]] = relationship(
        "RevisionHistory", back_populates="item", order_by="RevisionHistory.revised_at"
    )


# ── Images (physical pages; always belong to an Item) ─────────────────────────

class Image(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey("collections.id"), nullable=False)
    item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("items.id"), nullable=True)
    page_number: Mapped[int] = mapped_column(Integer, default=1)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    filepath: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64))
    ingested_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    collection: Mapped["Collection"] = relationship("Collection")
    item: Mapped[Optional["Item"]] = relationship("Item", back_populates="pages")


# ── Metadata records ──────────────────────────────────────────────────────────

class MetadataRecord(Base):
    __tablename__ = "metadata_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("items.id"), nullable=True, unique=True)

    title: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    visible_text: Mapped[Optional[str]] = mapped_column(Text)
    subjects: Mapped[Optional[str]] = mapped_column(Text)       # JSON list
    people: Mapped[Optional[str]] = mapped_column(Text)         # JSON list
    places: Mapped[Optional[str]] = mapped_column(Text)         # JSON list
    dates: Mapped[Optional[str]] = mapped_column(String(200))
    objects: Mapped[Optional[str]] = mapped_column(Text)        # JSON list
    uncertainty_notes: Mapped[Optional[str]] = mapped_column(Text)
    reviewer_notes: Mapped[Optional[str]] = mapped_column(Text)

    review_status: Mapped[str] = mapped_column(
        String(50), default="needs_review", nullable=False
    )
    draft_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    last_revised_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    approved_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    approved_by: Mapped[Optional[str]] = mapped_column(String(200))

    item: Mapped[Optional["Item"]] = relationship("Item", back_populates="metadata_record")

    def get_tags(self, field: str) -> list[str]:
        raw = getattr(self, field, None)
        if not raw:
            return []
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return [t.strip() for t in raw.split(",") if t.strip()]

    def set_tags(self, field: str, values: list[str]) -> None:
        setattr(self, field, json.dumps(values))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "item_id": self.item_id,
            "title": self.title,
            "description": self.description,
            "visible_text": self.visible_text,
            "subjects": self.get_tags("subjects"),
            "people": self.get_tags("people"),
            "places": self.get_tags("places"),
            "dates": self.dates,
            "objects": self.get_tags("objects"),
            "uncertainty_notes": self.uncertainty_notes,
            "reviewer_notes": self.reviewer_notes,
            "review_status": self.review_status,
            "draft_generated": self.draft_generated,
            "last_revised_at": self.last_revised_at.isoformat() if self.last_revised_at else None,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "approved_by": self.approved_by,
        }


# ── Revision history (append-only audit log) ─────────────────────────────────

class RevisionHistory(Base):
    __tablename__ = "revision_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("items.id"), nullable=True)
    revision_type: Mapped[str] = mapped_column(String(50))
    metadata_snapshot: Mapped[str] = mapped_column(Text)
    feedback_given: Mapped[Optional[str]] = mapped_column(Text)
    revised_by: Mapped[str] = mapped_column(String(100), default="system")
    revised_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    item: Mapped[Optional["Item"]] = relationship("Item", back_populates="history")


# ── Engine / session factory ──────────────────────────────────────────────────

def get_engine():
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def set_wal(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA journal_mode=WAL")

    return engine


def create_tables(engine=None):
    if engine is None:
        engine = get_engine()
    Base.metadata.create_all(engine)
    return engine


def get_session(engine=None) -> Session:
    from sqlalchemy.orm import sessionmaker
    if engine is None:
        engine = get_engine()
    SessionLocal = sessionmaker(bind=engine, autoflush=False)
    return SessionLocal()
