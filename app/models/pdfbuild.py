"""Build a searchable PDF from page JPEGs + per-word boxes, with an invisible,
position-aligned text layer (per-word horizontal scaling so selection/highlight
lands on whole words). Ported from the Bodega pipeline.
"""
from __future__ import annotations
import os
from typing import Dict, List

import fitz  # PyMuPDF

DPI = 200.0
_PT = 72.0 / DPI  # image pixels -> PDF points


def _insert_words(page: "fitz.Page", words: List[Dict], page_rect: "fitz.Rect") -> None:
    W, H = page_rect.width, page_rect.height
    for ln in words:
        txt = (ln.get("text") or "").strip()
        box = ln.get("bbox")
        if not txt or not box or len(box) != 4:
            continue
        x0, y0, x1, y1 = (box[0] * _PT, box[1] * _PT, box[2] * _PT, box[3] * _PT)
        if x1 < x0:
            x0, x1 = x1, x0
        if y1 < y0:
            y0, y1 = y1, y0
        bw = x1 - x0
        fs = max(2.0, (y1 - y0) * 0.85)
        bx = min(max(x0, 0.0), W - 1)
        by = min(max(y1 - (y1 - y0) * 0.12, fs), H - 1)
        try:
            natural = fitz.get_text_length(txt, fontname="helv", fontsize=fs)
            hscale = max(0.2, min(bw / natural, 6.0)) if natural > 0.1 else 1.0
            page.insert_text((bx, by), txt, fontsize=fs, fontname="helv",
                             render_mode=3,
                             morph=(fitz.Point(bx, by), fitz.Matrix(hscale, 1.0)))
        except Exception:  # noqa: BLE001
            pass


def build_searchable_pdf(jpg_paths: List[str], words_per_page: List[List[Dict]],
                         out_path: str, meta: Dict = None) -> str:
    doc = fitz.open()
    for jpg, words in zip(jpg_paths, words_per_page):
        pix = fitz.Pixmap(jpg)
        w_pt, h_pt = pix.width * _PT, pix.height * _PT
        page = doc.new_page(width=w_pt, height=h_pt)
        rect = fitz.Rect(0, 0, w_pt, h_pt)
        page.insert_image(rect, filename=jpg)
        if words:
            _insert_words(page, words, rect)
        pix = None
    if meta:
        doc.set_metadata({"title": meta.get("title", "") or "",
                          "producer": "metadata-generator"})
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tmp = out_path + ".tmp"
    doc.save(tmp, deflate=True, garbage=4)
    doc.close()
    os.replace(tmp, out_path)
    return out_path
