"""
api/routes/collections.py

GET  /api/collections
POST /api/collections
GET  /api/collections/{id}
PUT  /api/collections/{id}
GET  /api/collections/{id}/stats
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.deps import get_db
from app.db import crud

router = APIRouter()


class CollectionIn(BaseModel):
    name: str
    description_style: Optional[str] = None
    controlled_vocabulary: Optional[str] = None
    known_locations: Optional[str] = None
    known_date_range: Optional[str] = None
    known_people_orgs: Optional[str] = None
    terms_to_avoid: Optional[str] = None
    institutional_rules: Optional[str] = None
    rights_sensitivity_notes: Optional[str] = None


def _serialize(c) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "description_style": c.description_style,
        "controlled_vocabulary": c.controlled_vocabulary,
        "known_locations": c.known_locations,
        "known_date_range": c.known_date_range,
        "known_people_orgs": c.known_people_orgs,
        "terms_to_avoid": c.terms_to_avoid,
        "institutional_rules": c.institutional_rules,
        "rights_sensitivity_notes": c.rights_sensitivity_notes,
        "created_at": c.created_at.isoformat(),
    }


@router.get("/collections")
def list_collections(db: Session = Depends(get_db)):
    return [_serialize(c) for c in crud.list_collections(db)]


@router.post("/collections", status_code=201)
def create_collection(body: CollectionIn, db: Session = Depends(get_db)):
    coll = crud.get_or_create_collection(db, **body.model_dump())
    return _serialize(coll)


@router.get("/collections/{collection_id}")
def get_collection(collection_id: int, db: Session = Depends(get_db)):
    colls = crud.list_collections(db)
    coll = next((c for c in colls if c.id == collection_id), None)
    if not coll:
        raise HTTPException(status_code=404, detail="Collection not found")
    return _serialize(coll)


@router.put("/collections/{collection_id}")
def update_collection(collection_id: int, body: CollectionIn, db: Session = Depends(get_db)):
    try:
        coll = crud.update_collection(db, collection_id, **body.model_dump(exclude={"name"}))
    except Exception:
        raise HTTPException(status_code=404, detail="Collection not found")
    return _serialize(coll)


@router.get("/collections/{collection_id}/stats")
def collection_stats(collection_id: int, db: Session = Depends(get_db)):
    return crud.status_counts(db, collection_id=collection_id)
