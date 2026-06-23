"""Tesseract word-level boxes for the aligned PDF text layer (CPU, local).

Qwen does the OCR text (quality); Tesseract supplies the geometry so the
invisible PDF text layer aligns with the image. No GPU dependency.
"""
from __future__ import annotations
import csv
import io
import subprocess
from typing import Dict, List

from app.config import TESSERACT_BIN, TESS_LANG


def tesseract_words(jpg_path: str) -> List[Dict]:
    """[{text, bbox:[x0,y0,x1,y1]}] in image-pixel coords; [] on failure."""
    try:
        out = subprocess.run(
            [TESSERACT_BIN, jpg_path, "stdout", "-l", TESS_LANG, "--psm", "3", "tsv"],
            capture_output=True, text=True, timeout=180,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return []
    words: List[Dict] = []
    for row in csv.DictReader(io.StringIO(out), delimiter="\t", quoting=csv.QUOTE_NONE):
        try:
            if row.get("level") != "5":          # 5 = word
                continue
            txt = (row.get("text") or "").strip()
            if not txt or float(row.get("conf", "-1")) < 0:
                continue
            l, t = int(row["left"]), int(row["top"])
            w, h = int(row["width"]), int(row["height"])
            words.append({"text": txt, "bbox": [l, t, l + w, t + h]})
        except (ValueError, KeyError, TypeError):
            continue
    return words
