"""
api/deps.py — shared FastAPI dependencies.
"""
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from sqlalchemy.orm import Session

from app.db.schema import create_tables, get_session

# Ensure tables exist before the first request hits any route.
create_tables()


def get_db() -> Session:
    db = get_session()
    try:
        yield db
    finally:
        db.close()
