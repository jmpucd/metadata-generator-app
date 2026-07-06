"""Document branch: auto-detect textual documents, OCR them page-by-page with
the vision model, derive metadata from the transcription, and build a searchable
(Tesseract-aligned) PDF. Backend-agnostic: the caller passes in `infer`
(normal-res vision call) and `ocr_infer` (high-res single-page call).
"""
from __future__ import annotations
import logging
import os
from typing import Callable, Dict, List

log = logging.getLogger(__name__)

_CLASSIFY_PROMPT = (
    "Look at this scanned item. Is it primarily a TEXTUAL DOCUMENT (typed or "
    "handwritten text — a letter, form, report, menu, ledger, note) or a "
    "PHOTOGRAPH / visual image (people, places, objects, scenes)? "
    "Answer with exactly one word: document OR photo."
)

_OCR_PROMPT = (
    "You are an OCR engine. Transcribe ALL text on this page verbatim, preserving "
    "reading order and line breaks. Do not summarize or add commentary. If the page "
    "has no readable text, output exactly: [BLANK]"
)


def classify_doc_type(image_paths: List[str], infer: Callable) -> str:
    try:
        raw = infer(image_paths[:1], _CLASSIFY_PROMPT).strip().lower()
    except Exception as e:  # noqa: BLE001
        log.warning("classify failed (%s); defaulting to photo", e)
        return "photo"
    return "document" if "document" in raw[:40] else "photo"


def ocr_pages(image_paths: List[str], ocr_infer: Callable) -> List[str]:
    """Full verbatim transcription, one page per call (no truncation/summarizing)."""
    out = []
    for p in image_paths:
        try:
            t = ocr_infer([p], _OCR_PROMPT).strip()
        except Exception as e:  # noqa: BLE001
            log.warning("OCR failed on %s: %s", p, e)
            t = ""
        out.append("" if t == "[BLANK]" else t)
    return out


def _doc_metadata_prompt(full_text: str, ctx: dict) -> str:
    head = []
    if ctx.get("collection_name"):
        head.append(f"Collection: {ctx['collection_name']}")
    if ctx.get("institutional_rules"):
        head.append(f"Institutional rules: {ctx['institutional_rules']}")
    excerpt = full_text[:8000]
    return (
        "You are a library metadata specialist describing a textual document for a "
        "digital archive. Below is the document's OCR transcription.\n\n"
        + ("\n".join(head) + "\n\n" if head else "")
        + "TRANSCRIPTION:\n" + excerpt + "\n\n"
        "Return ONLY a JSON object with these keys: "
        '{"title": "...", "description": "...", "subjects": [..], "people": [..], '
        '"places": [..], "dates": "...", "objects": [..], "uncertainty_notes": "..."}. '
        "Base it on the transcription (and the page image). Title = a concise descriptive "
        "title for the document. Description = what the document is and its content. "
        "Do not invent facts. Return ONLY the JSON object — no markdown fences."
    )


def doc_metadata(full_text: str, image_paths: List[str], infer: Callable,
                 parse_json: Callable, ctx: dict) -> dict:
    try:
        raw = infer(image_paths[:1], _doc_metadata_prompt(full_text, ctx))
        return parse_json(raw)
    except Exception as e:  # noqa: BLE001
        log.warning("doc metadata failed: %s", e)
        return {}


def _item_name(image_paths: List[str]) -> str:
    first = image_paths[0]
    if len(image_paths) > 1:
        return os.path.basename(os.path.dirname(first)) or os.path.splitext(os.path.basename(first))[0]
    return os.path.splitext(os.path.basename(first))[0]


def build_pdf(image_paths: List[str], title: str) -> str:
    from digtk.words import tesseract_words
    from digtk.pdfbuild import build_searchable_pdf
    from app.config import PDF_DIR, TESSERACT_BIN, TESS_LANG
    from digtk import config as dtk_config
    dtk_config.TESSERACT_BIN, dtk_config.TESS_LANG = TESSERACT_BIN, TESS_LANG
    words = [tesseract_words(p) for p in image_paths]
    out = os.path.join(str(PDF_DIR), _item_name(image_paths) + ".pdf")
    return build_searchable_pdf(image_paths, words, out, meta={"title": title},
                                producer="metadata-generator")


def process_document(image_paths: List[str], ctx: dict, infer: Callable,
                     ocr_infer: Callable, parse_json: Callable) -> dict:
    page_texts = ocr_pages(image_paths, ocr_infer)
    parts = [f"[page {i + 1}]\n{t}" for i, t in enumerate(page_texts) if t]
    full_text = "\n\n".join(parts)
    md = doc_metadata(full_text, image_paths, infer, parse_json, ctx)

    pdf_path = None
    try:
        pdf_path = build_pdf(image_paths, md.get("title") or _item_name(image_paths))
    except Exception as e:  # noqa: BLE001
        log.warning("searchable PDF build failed: %s", e)

    result = {
        "doc_type": "document",
        "full_ocr_text": full_text,
        "visible_text": full_text[:20000],
        "generated_pdf_path": pdf_path,
    }
    for k in ("title", "description", "subjects", "people", "places", "dates",
              "objects", "uncertainty_notes"):
        if md.get(k) is not None:
            result[k] = md[k]
    return result
