"""
app/config.py — central configuration for the photo review app.
Edit paths and defaults here, or override via environment variables.
"""
from pathlib import Path
import os

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent   # project root
DATA_DIR = BASE_DIR / "data"
IMAGES_DIR = Path(os.getenv("IMAGES_DIR", str(BASE_DIR / "images" / "incoming")))
METADATA_DIR = DATA_DIR / "metadata"
EXPORTS_DIR = DATA_DIR / "exports"
DB_PATH = METADATA_DIR / "review.db"

# Auto-create directories on import
for _dir in (IMAGES_DIR, METADATA_DIR, EXPORTS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_PATH}"

# ── Local VLM settings ─────────────────────────────────────────────────────────
# Change MODEL_BACKEND to "ollama" or "mock" to swap the backend without
# touching any other code.
MODEL_BACKEND: str = os.getenv("MODEL_BACKEND", "ollama")  # qwen_vl | ollama | mock

# Qwen-VL
QWEN_MODEL_ID: str = os.getenv("QWEN_MODEL_ID", "Qwen/Qwen2-VL-7B-Instruct")
QWEN_DEVICE: str = os.getenv("QWEN_DEVICE", "cpu")           # "cuda" if you have a GPU

# Ollama (alternative backend)
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "https://samwise.library.ucdavis.edu/ollama")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5vl:32b")
OLLAMA_TOKEN: str = os.getenv("OLLAMA_TOKEN", "")

# Claude API backend
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-opus-4-7")

# ── Metadata fields ────────────────────────────────────────────────────────────
# These drive both the DB schema and the UI form.
METADATA_FIELDS: list[dict] = [
    {"key": "title",             "label": "Title",                 "type": "text",     "required": True},
    {"key": "description",       "label": "Description",           "type": "textarea", "required": True},
    {"key": "visible_text",      "label": "Visible Text / OCR",    "type": "textarea", "required": False},
    {"key": "subjects",          "label": "Subjects / Keywords",   "type": "tags",     "required": False},
    {"key": "people",            "label": "People",                "type": "tags",     "required": False},
    {"key": "places",            "label": "Places",                "type": "tags",     "required": False},
    {"key": "dates",             "label": "Dates",                 "type": "text",     "required": False},
    {"key": "objects",           "label": "Objects",               "type": "tags",     "required": False},
    {"key": "uncertainty_notes", "label": "Uncertainty Notes",     "type": "textarea", "required": False},
    {"key": "reviewer_notes",    "label": "Reviewer Notes",        "type": "textarea", "required": False},
]

REVIEW_STATUSES = ["queue", "working", "ready", "hold", "exported"]

# ── Streamlit page config ──────────────────────────────────────────────────────
PAGE_TITLE = "Photo Metadata Review"
PAGE_ICON = "🖼️"
THUMBNAIL_MAX_PX = 900
OLLAMA_IMAGE_MAX_PX: int = int(os.getenv("OLLAMA_IMAGE_MAX_PX", "2048"))
OLLAMA_IMAGE_QUALITY: int = int(os.getenv("OLLAMA_IMAGE_QUALITY", "85"))
