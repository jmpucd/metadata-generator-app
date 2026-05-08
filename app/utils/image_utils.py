"""
app/utils/image_utils.py — image path helpers and thumbnail generation.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from app.config import THUMBNAIL_MAX_PX

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".gif", ".bmp", ".webp"}


def find_images(folder: str | Path) -> list[Path]:
    """Recursively find all supported image files in a folder."""
    folder = Path(folder)
    return sorted(
        p for p in folder.rglob("*")
        if p.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def make_thumbnail_bytes(path: str | Path, max_px: int = THUMBNAIL_MAX_PX) -> bytes:
    """
    Return a JPEG-encoded thumbnail as bytes.
    Streamlit can display these with st.image(bytes).
    """
    from PIL import Image, ImageOps
    img = Image.open(path).convert("RGB")
    img = ImageOps.exif_transpose(img)          # auto-rotate based on EXIF
    img.thumbnail((max_px, max_px), Image.LANCZOS)
    import io
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()
