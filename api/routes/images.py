"""
api/routes/images.py

GET /api/collections/{id}/images?status=...
GET /api/images/{id}
GET /api/images/{id}/file
GET /api/images/{id}/thumbnail
"""
import mimetypes
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from api.deps import get_db
from app.db import crud
from app.utils.image_utils import make_thumbnail_bytes

router = APIRouter()


def _serialize(img) -> dict:
    rec = img.metadata_record
    return {
        "id": img.id,
        "filename": img.filename,
        "filepath": img.filepath,
        "collection_id": img.collection_id,
        "ingested_at": img.ingested_at.isoformat(),
        "status": rec.review_status if rec else "needs_review",
        "draft_generated": rec.draft_generated if rec else False,
    }


@router.get("/collections/{collection_id}/images")
def list_images(
    collection_id: int,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    # "all" is a UI sentinel — treat as no filter
    status_filter = None if (not status or status == "all") else status
    images = crud.list_images(db, collection_id=collection_id, status=status_filter)
    return [_serialize(img) for img in images]


@router.get("/images/{image_id}")
def get_image(image_id: int, db: Session = Depends(get_db)):
    img = crud.get_image(db, image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")
    return _serialize(img)


@router.get("/images/{image_id}/file")
def serve_image_file(image_id: int, db: Session = Depends(get_db)):
    img = crud.get_image(db, image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")
    path = Path(img.filepath)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found on disk: {img.filepath}")
    media_type, _ = mimetypes.guess_type(str(path))
    return FileResponse(str(path), media_type=media_type or "application/octet-stream")


@router.get("/images/{image_id}/thumbnail")
def serve_thumbnail(image_id: int, db: Session = Depends(get_db)):
    img = crud.get_image(db, image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")
    path = Path(img.filepath)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found on disk: {img.filepath}")
    thumb = make_thumbnail_bytes(str(path))
    return Response(content=thumb, media_type="image/jpeg")
