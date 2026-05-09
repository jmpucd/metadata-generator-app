"""
api/routes/status.py

PATCH /api/metadata/{image_id}/status
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.deps import get_db
from app.db import crud
from app.config import REVIEW_STATUSES

router = APIRouter()


class StatusIn(BaseModel):
    status: str


@router.patch("/metadata/{image_id}/status")
def set_status(image_id: int, body: StatusIn, db: Session = Depends(get_db)):
    if body.status not in REVIEW_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status '{body.status}'. Must be one of: {REVIEW_STATUSES}",
        )
    img = crud.get_image(db, image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")
    if body.status == "approved":
        crud.snapshot_revision(db, image_id, "approved", revised_by="reviewer")
    rec = crud.set_review_status(db, image_id, body.status)
    return {"image_id": image_id, "status": rec.review_status}
