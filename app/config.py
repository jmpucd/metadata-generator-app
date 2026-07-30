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
MODEL_BACKEND: str = os.getenv("MODEL_BACKEND", "ollama")  # qwen_vl | ollama | vllm | mock

# Qwen-VL
QWEN_MODEL_ID: str = os.getenv("QWEN_MODEL_ID", "Qwen/Qwen2-VL-7B-Instruct")
QWEN_DEVICE: str = os.getenv("QWEN_DEVICE", "cpu")           # "cuda" if you have a GPU

# Ollama (alternative backend)
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "https://samwise.library.ucdavis.edu/ollama")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5vl:32b")
OLLAMA_TOKEN: str = os.getenv("OLLAMA_TOKEN", "")

# vLLM backend (OpenAI-compatible), via digtk.vllm_client. Base URL should end in
# /api (Open WebUI/samwise) or /v1 (bare vLLM); a bare host gets /v1 appended for
# back-compat with old cyberdyne-style .env values. samwise requires VLLM_TOKEN.
VLLM_BASE_URL: str = os.getenv("VLLM_BASE_URL", "https://samwise.library.ucdavis.edu/api")
VLLM_MODEL: str = os.getenv("VLLM_MODEL", "qwen3.6-fast:35b")
VLLM_TOKEN: str = os.getenv("VLLM_TOKEN", "")
VLLM_IMAGE_MAX_PX: int = int(os.getenv("VLLM_IMAGE_MAX_PX", "1024"))

PROMPT_STYLE: str = os.getenv("PROMPT_STYLE", "full")  # full | minimal

# Reusable prompt modules ("packs") — see app/prompt_packs.py. Collections opt in by
# listing pack names in Collection.prompt_packs.
PACKS_DIR = Path(os.getenv("PACKS_DIR", str(BASE_DIR / "prompts" / "packs")))

# Claude API backend
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-opus-4-7")

# ── Concurrency ─────────────────────────────────────────────────────────────
# Items processed in parallel by `generate` (vision calls are I/O-bound; the GPU
# batches across requests). DB writes stay single-threaded.
GENERATE_WORKERS: int = int(os.getenv("GENERATE_WORKERS", "6"))

# ── Endpoint resilience ─────────────────────────────────────────────────────
VLLM_CONNECT_TIMEOUT: float = float(os.getenv("VLLM_CONNECT_TIMEOUT", "15"))
VLLM_READ_TIMEOUT: float = float(os.getenv("VLLM_READ_TIMEOUT", "600"))
VLLM_RETRIES: int = int(os.getenv("VLLM_RETRIES", "6"))  # exp backoff, survives brief blips

# ── Nightly maintenance window (pause between items) ────────────────────────
# "HH:MM" 24h local server time; both empty = disabled. Wraps midnight.
MAINT_PAUSE_START: str = os.getenv("MAINT_PAUSE_START", "")  # e.g. "00:00"
MAINT_PAUSE_END: str = os.getenv("MAINT_PAUSE_END", "")      # e.g. "02:00"

# ── Document mode (OCR + searchable PDF for textual documents) ──────────────
DOC_DETECT: bool = os.getenv("DOC_DETECT", "true").lower() in ("1", "true", "yes")
DOC_OCR_MAX_PX: int = int(os.getenv("DOC_OCR_MAX_PX", "2200"))   # higher res for OCR
PDF_DIR = Path(os.getenv("PDF_DIR", str(EXPORTS_DIR / "pdfs")))
PDF_DIR.mkdir(parents=True, exist_ok=True)
TESSERACT_BIN: str = os.getenv("TESSERACT_BIN", "tesseract")
TESS_LANG: str = os.getenv("TESS_LANG", "eng")

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
# Note: doc_type / full_ocr_text / generated_pdf_path are DB columns set by the
# pipeline (not prompt fields), so they're intentionally NOT in METADATA_FIELDS.

REVIEW_STATUSES = ["queue", "working", "ready", "hold", "exported"]

# ── Streamlit page config ──────────────────────────────────────────────────────
PAGE_TITLE = "Photo Metadata Review"
PAGE_ICON = "🖼️"
THUMBNAIL_MAX_PX = 900
OLLAMA_IMAGE_MAX_PX: int = int(os.getenv("OLLAMA_IMAGE_MAX_PX", "2048"))
OLLAMA_IMAGE_QUALITY: int = int(os.getenv("OLLAMA_IMAGE_QUALITY", "85"))
