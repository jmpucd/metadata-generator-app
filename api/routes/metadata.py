"""
api/routes/metadata.py

GET /api/metadata/{image_id}
PUT /api/metadata/{image_id}
GET /api/metadata/{image_id}/history
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.deps import get_db
from app.db import crud

router = APIRouter()


class MetadataIn(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    visible_text: Optional[str] = None
    subjects: Optional[List[str]] = None
    people: Optional[List[str]] = None
    places: Optional[List[str]] = None
    dates: Optional[str] = None
    objects: Optional[List[str]] = None
    uncertainty_notes: Optional[str] = None
    reviewer_notes: Optional[str] = None


@router.get("/metadata/{image_id}")
def get_metadata(image_id: int, db: Session = Depends(get_db)):
    rec = crud.get_metadata(db, image_id)
    if not rec:
        raise HTTPException(status_code=404, detail="No metadata record for this image")
    return rec.to_dict()


@router.put("/metadata/{image_id}")
def update_metadata(image_id: int, body: MetadataIn, db: Session = Depends(get_db)):
    img = crud.get_image(db, image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")
    fields = body.model_dump(exclude_none=True)
    crud.snapshot_revision(db, image_id, "human_edit", revised_by="reviewer")
    rec = crud.upsert_metadata(db, image_id, fields)
    return rec.to_dict()


@router.get("/metadata/{image_id}/history")
def get_history(image_id: int, db: Session = Depends(get_db)):
    history = crud.get_revision_history(db, image_id)
    return [
        {
            "id": h.id,
            "revision_type": h.revision_type,
            "revised_by": h.revised_by,
            "revised_at": h.revised_at.isoformat(),
            "feedback_given": h.feedback_given,
            "snapshot": h.metadata_snapshot,  # JSON string — client parses if needed
        }
        for h in history
    ]
