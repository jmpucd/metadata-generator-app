"""
api/routes/export.py

GET /api/collections/{id}/export?format=csv|json
"""
import csv
import io
import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from api.deps import get_db
from app.db import crud

router = APIRouter()


@router.get("/collections/{collection_id}/export")
def export(
    collection_id: int,
    format: Literal["csv", "json"] = Query(default="csv"),
    db: Session = Depends(get_db),
):
    pairs = crud.get_approved_records(db, collection_id=collection_id)
    if not pairs:
        raise HTTPException(status_code=404, detail="No approved records in this collection")

    rows = []
    for item, rec in pairs:
        rep = item.pages[0] if item.pages else None
        rows.append({
            "item_key":          item.item_key,
            "series":            item.series or "",
            "filename":          rep.filename if rep else "",
            "filepath":          rep.filepath if rep else "",
            "page_count":        len(item.pages),
            "title":             rec.title or "",
            "description":       rec.description or "",
            "visible_text":      rec.visible_text or "",
            "subjects":          rec.get_tags("subjects"),
            "people":            rec.get_tags("people"),
            "places":            rec.get_tags("places"),
            "dates":             rec.dates or "",
            "objects":           rec.get_tags("objects"),
            "uncertainty_notes": rec.uncertainty_notes or "",
            "reviewer_notes":    rec.reviewer_notes or "",
            "review_status":     rec.review_status,
            "approved_at":       rec.approved_at.isoformat() if rec.approved_at else "",
        })

    if format == "json":
        content = json.dumps(rows, indent=2, ensure_ascii=False)
        return Response(
            content=content.encode(),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=collection_{collection_id}.json"},
        )

    # CSV — flatten list fields to semicolon-separated strings
    buf = io.StringIO()
    fieldnames = [
        "item_key", "series", "filename", "page_count",
        "title", "description", "visible_text",
        "subjects", "people", "places", "dates", "objects",
        "uncertainty_notes", "reviewer_notes", "approved_at",
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        flat = dict(row)
        for f in ("subjects", "people", "places", "objects"):
            flat[f] = "; ".join(flat[f])
        writer.writerow(flat)

    buf.seek(0)
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=collection_{collection_id}_approved.csv"
        },
    )
