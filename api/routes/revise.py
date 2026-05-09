"""
api/routes/revise.py

POST /api/metadata/{image_id}/revise

Calls the configured VLM backend (Ollama / Claude / mock) with the
reviewer's feedback and returns updated metadata.  Runs synchronously —
Ollama at 600s timeout means this can be slow; the frontend should show
a loading state and not time out early.
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


@router.post("/metadata/{image_id}/revise")
def revise(image_id: int, body: ReviseIn, db: Session = Depends(get_db)):
    if not body.feedback.strip():
        raise HTTPException(status_code=422, detail="feedback must not be empty")

    img = crud.get_image(db, image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")

    rec = crud.get_metadata(db, image_id)
    if not rec:
        raise HTTPException(
            status_code=400,
            detail="No metadata record — generate a draft first via the CLI",
        )

    try:
        revised = vlm_revise(
            image_path=img.filepath,
            current_metadata=rec.to_dict(),
            feedback=body.feedback,
            session_context=img.collection.session_context(),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"VLM error: {exc}") from exc

    crud.snapshot_revision(db, image_id, "model_revision", feedback=body.feedback)
    updated = crud.upsert_metadata(db, image_id, revised)
    crud.set_review_status(db, image_id, "revised")
    return updated.to_dict()
