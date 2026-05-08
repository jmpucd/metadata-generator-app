"""
app/db/schema.py — SQLAlchemy ORM models.

Tables
------
collections     One row per review session / collection.
images          One row per ingested image file.
metadata_records  Current metadata for an image (one active row per image).
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
    controlled_vocabulary: Mapped[Optional[str]] = mapped_column(Text)   # free text / JSON list
    known_locations: Mapped[Optional[str]] = mapped_column(Text)
    known_date_range: Mapped[Optional[str]] = mapped_column(String(100))
    known_people_orgs: Mapped[Optional[str]] = mapped_column(Text)
    terms_to_avoid: Mapped[Optional[str]] = mapped_column(Text)
    institutional_rules: Mapped[Optional[str]] = mapped_column(Text)
    rights_sensitivity_notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    images: Mapped[list["Image"]] = relationship("Image", back_populates="collection")

    def session_context(self) -> dict:
        """Return a plain dict suitable for passing to the VLM prompt builder."""
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


# ── Images ────────────────────────────────────────────────────────────────────

class Image(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey("collections.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    filepath: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64))   # sha256
    ingested_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    collection: Mapped["Collection"] = relationship("Collection", back_populates="images")
    metadata_record: Mapped[Optional["MetadataRecord"]] = relationship(
        "MetadataRecord", back_populates="image", uselist=False
    )
    history: Mapped[list["RevisionHistory"]] = relationship(
        "RevisionHistory", back_populates="image", order_by="RevisionHistory.revised_at"
    )


# ── Metadata records ──────────────────────────────────────────────────────────

class MetadataRecord(Base):
    __tablename__ = "metadata_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    image_id: Mapped[int] = mapped_column(ForeignKey("images.id"), nullable=False, unique=True)

    # Core fields (plain text; tags stored as JSON-encoded lists)
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

    # Workflow
    review_status: Mapped[str] = mapped_column(
        String(50), default="needs_review", nullable=False
    )
    draft_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    last_revised_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    approved_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    approved_by: Mapped[Optional[str]] = mapped_column(String(200))

    image: Mapped["Image"] = relationship("Image", back_populates="metadata_record")

    # ── Helpers for tag fields ────────────────────────────────────────────────

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
            "image_id": self.image_id,
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
    image_id: Mapped[int] = mapped_column(ForeignKey("images.id"), nullable=False)
    revision_type: Mapped[str] = mapped_column(String(50))  # "draft" | "human_edit" | "model_revision" | "approved"
    metadata_snapshot: Mapped[str] = mapped_column(Text)    # JSON dump of MetadataRecord at this point
    feedback_given: Mapped[Optional[str]] = mapped_column(Text)  # reviewer's instruction to the model
    revised_by: Mapped[str] = mapped_column(String(100), default="system")
    revised_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    image: Mapped["Image"] = relationship("Image", back_populates="history")


# ── Engine / session factory ──────────────────────────────────────────────────

def get_engine():
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    # Enable WAL mode for SQLite so reads don't block writes
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
