"""
api/routes/status.py

PATCH /api/metadata/{item_id}/status
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


@router.patch("/metadata/{item_id}/status")
def set_status(item_id: int, body: StatusIn, db: Session = Depends(get_db)):
    if body.status not in REVIEW_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status '{body.status}'. Must be one of: {REVIEW_STATUSES}",
        )
    item = crud.get_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if body.status == "ready":
        crud.snapshot_revision(db, item_id, "ready", revised_by="reviewer")
    rec = crud.set_review_status(db, item_id, body.status)
    return {"item_id": item_id, "status": rec.review_status}
