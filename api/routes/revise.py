"""
api/routes/revise.py

POST /api/metadata/{item_id}/revise
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.deps import get_db
from app.db import crud
from app.models.local_vlm import revise_metadata as vlm_revise

router = APIRouter()


class ReviseIn(BaseModel):
    feedback: str


@router.post("/metadata/{item_id}/revise")
def revise(item_id: int, body: ReviseIn, db: Session = Depends(get_db)):
    if not body.feedback.strip():
        raise HTTPException(status_code=422, detail="feedback must not be empty")

    item = crud.get_item(db, item_id)
    if not item or not item.pages:
        raise HTTPException(status_code=404, detail="Item not found or has no pages")

    rec = crud.get_metadata(db, item_id)
    if not rec:
        raise HTTPException(
            status_code=400,
            detail="No metadata record — generate a draft first via the CLI",
        )

    try:
        revised = vlm_revise(
            image_paths=[p.filepath for p in item.pages],
            current_metadata=rec.to_dict(),
            feedback=body.feedback,
            session_context=item.collection.session_context(),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"VLM error: {exc}") from exc

    crud.snapshot_revision(db, item_id, "model_revision", feedback=body.feedback)
    updated = crud.upsert_metadata(db, item_id, revised)
    crud.set_review_status(db, item_id, "working")
    return updated.to_dict()
