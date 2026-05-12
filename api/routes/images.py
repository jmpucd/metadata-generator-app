"""
api/routes/images.py

GET /api/collections/{id}/items?status=...   — list items with pages
GET /api/images/{id}/file                    — serve image file
GET /api/images/{id}/thumbnail               — serve thumbnail
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


def _serialize_item(item) -> dict:
    rec = item.metadata_record
    return {
        "id": item.id,
        "collection_id": item.collection_id,
        "series": item.series or "",
        "item_key": item.item_key,
        "status": rec.review_status if rec else "needs_review",
        "draft_generated": rec.draft_generated if rec else False,
        "pages": [
            {
                "id": page.id,
                "filename": page.filename,
                "filepath": page.filepath,
                "page_number": page.page_number,
            }
            for page in item.pages
        ],
    }


@router.get("/collections/{collection_id}/items")
def list_items(
    collection_id: int,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    status_filter = None if (not status or status == "all") else status
    items = crud.list_items(db, collection_id=collection_id, status=status_filter)
    return [_serialize_item(item) for item in items]


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
