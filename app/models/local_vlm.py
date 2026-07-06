"""
app/models/local_vlm.py
=======================
Local vision-language model backend.

Public interface (two functions every backend must expose):
    generate_metadata(image_path, session_context) -> dict
    revise_metadata(image_path, current_metadata, feedback, session_context) -> dict

Set MODEL_BACKEND in app/config.py (or via env var) to choose:
    "qwen_vl"  — Qwen2-VL via HuggingFace transformers
    "ollama"   — any Ollama-served multimodal model (LLaVA, moondream, etc.)
    "mock"     — deterministic stub for development / testing (no GPU needed)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from app.config import MODEL_BACKEND, METADATA_FIELDS

log = logging.getLogger(__name__)

# ── Prompt builders ───────────────────────────────────────────────────────────

def _build_generate_prompt(session_context: dict) -> str:
    ctx = session_context
    field_list = "\n".join(
        f'  "{f["key"]}": "<value or empty string>"'
        for f in METADATA_FIELDS
    )
    lines = [
        "You are a library metadata specialist analysing a photograph for a digital archive.",
        "",
    ]
    if ctx.get("collection_name"):
        lines.append(f"Collection: {ctx['collection_name']}")
    if ctx.get("description_style"):
        lines.append(f"Description style: {ctx['description_style']}")
    if ctx.get("known_locations"):
        lines.append(f"Known locations: {ctx['known_locations']}")
    if ctx.get("known_date_range"):
        lines.append(f"Known date range: {ctx['known_date_range']}")
    if ctx.get("known_people_orgs"):
        lines.append(f"Known people/organisations: {ctx['known_people_orgs']}")
    if ctx.get("controlled_vocabulary"):
        lines.append(f"Use these controlled vocabulary terms where appropriate: {ctx['controlled_vocabulary']}")
    if ctx.get("terms_to_avoid"):
        lines.append(f"Avoid these terms: {ctx['terms_to_avoid']}")
    if ctx.get("institutional_rules"):
        lines.append(f"Institutional rules: {ctx['institutional_rules']}")
    if ctx.get("rights_sensitivity_notes"):
        lines.append(f"Rights/sensitivity notes: {ctx['rights_sensitivity_notes']}")
    lines += [
        "",
        "Examine the photograph carefully and return ONLY a valid JSON object with these keys:",
        "{",
        field_list,
        "}",
        "",
        "Description guidelines:",
        "- Be specific about what is ACTUALLY VISIBLE — describe specific foods, clothing styles, furniture, architectural details, signage, and objects by name.",
        "- Note apparent ethnicity, age range, and gender of people only when clearly visible and relevant to the archival record.",
        "- Estimate the approximate decade (e.g. '1970s', 'early 2000s') from visible clues like clothing, hairstyles, technology, and photographic style.",
        "- Describe the physical setting in detail: room type, décor, lighting, visible architectural features.",
        "- Write in complete sentences in the past tense for description.",
        "- title: a concise descriptive title (5-10 words), not a generic label.",
        "",
        "Rules:",
        "- For list-type fields (subjects, people, places, objects), return a JSON array of strings.",
        "- subjects: use specific archival subject terms (e.g. 'Banquets', 'Wedding receptions', 'Street vendors'), not generic words like 'gathering'.",
        "- objects: list specific named objects visible in the image.",
        "- people: describe visible individuals by role, apparent age, clothing, or other observable characteristics — do not name unless a name is visible.",
        "- places: include specific location if identifiable from signage or context; otherwise describe the type of space.",
        "- visible_text: Transcribe all visible text exactly as it appears. For each foreign-language segment, identify the language in parentheses and add a translation in brackets immediately after — format: 原文 (Language) [translation: meaning]. Translate the full phrase for meaning — do NOT translate word-by-word or split compound phrases. Chinese compounds must be read as units: e.g. 歡迎光臨 = 'Welcome' (not 'welcome + visit'), 合影留念 = 'commemorative group photo' (not 'group photo + souvenir'). Example: '歡迎光臨曼谷大皇宮合影留念 (Traditional Chinese) [translation: Welcome to Bangkok Grand Palace — commemorative group photo] WELCOME TO BANGKOK GRAND PALACE'. Every non-English segment must have a language label and translation. If uncertain, use [translation?: probable meaning] and note it in uncertainty_notes. For partially legible text use [?best guess]. Use [illegible] only when nothing can be read. Use empty string if there is no text.",
        "- If you are uncertain about any value, note it in uncertainty_notes.",
        "- reviewer_notes: add any archival observations about approximate date, context, or significance that a cataloguer would find useful.",
        "- Return ONLY the JSON object — no markdown fences, no explanation.",
    ]
    return "\n".join(lines)


def _build_verso_prompt(session_context: dict) -> str:
    ctx = session_context
    field_list = "\n".join(
        f'  "{f["key"]}": "<value or empty string>"'
        for f in METADATA_FIELDS
    )
    recto_title = ctx.get("recto_title", "")
    recto_description = ctx.get("recto_description", "")
    lines = [
        "You are a library metadata specialist analysing the VERSO (back side) of a photograph for a digital archive.",
        "",
    ]
    if ctx.get("collection_name"):
        lines.append(f"Collection: {ctx['collection_name']}")
    if recto_title:
        lines.append(f"The front (recto) of this item is titled: \"{recto_title}\"")
    if recto_description:
        lines.append(f"Front side description: {recto_description}")
    lines += [
        "",
        "This image shows the BACK SIDE of the photograph above.",
        "",
        "Examine the back carefully and return ONLY a valid JSON object with these keys:",
        "{",
        field_list,
        "}",
        "",
        "Guidelines:",
        "- title: Use EXACTLY this format: 'Verso: back side of item depicting [3-7 word summary from the front description]'. If no front description is available, summarise what can be inferred.",
        "- description: Describe the physical condition of the back. Note any discoloration, foxing, water damage, yellowing, stains, fading, or paper texture. If blank, state that clearly.",
        "- visible_text: Transcribe text visible on the back verbatim. For each foreign-language segment, identify the language in parentheses and add a translation in brackets immediately after — format: 原文 (Language) [translation: meaning]. Example: '写真館 (Japanese) [translation: Photography Studio] TOKYO'. Every non-English segment must have a language label and translation. If uncertain, use [translation?: probable meaning] and note it in uncertainty_notes. For partially legible text use [?best guess]. Use [illegible] only when nothing can be read. Use empty string if there is no text.",
        "- IMPORTANT: Never state uncertain text as fact in the description field. If a watermark or brand name is faint or unclear, write 'faint printed text' or '[?Fujicolor]' rather than confidently naming a brand or institution you cannot clearly read.",
        "- subjects: Include 'Verso photographs'. Add further subjects only if derivable from visible text or markings.",
        "- people: Leave empty unless names are written or stamped on the back.",
        "- places: Leave empty unless a location is written on the back.",
        "- dates: Use any date written on the back; otherwise carry forward the estimated date from the front if available.",
        "- objects: List any stamps, stickers, labels, adhesive residue, or printed identifiers visible.",
        "- uncertainty_notes: Note if the verso is entirely blank, if handwriting is illegible, or if attribution to the recto is uncertain.",
        "- reviewer_notes: Note any archival significance of text or markings — donor inscriptions, photographer stamps, collection identifiers.",
        "- Return ONLY the JSON object — no markdown fences, no explanation.",
    ]
    if ctx.get("terms_to_avoid"):
        lines.append(f"Avoid these terms: {ctx['terms_to_avoid']}")
    if ctx.get("institutional_rules"):
        lines.append(f"Institutional rules: {ctx['institutional_rules']}")
    return "\n".join(lines)


def _build_revise_prompt(current_metadata: dict, feedback: str, session_context: dict) -> str:
    meta_str = json.dumps(current_metadata, indent=2, ensure_ascii=False)
    lines = [
        "You are a library metadata specialist revising existing metadata for a photograph.",
        "",
        "Current metadata:",
        meta_str,
        "",
        f"Reviewer instruction: {feedback}",
        "",
    ]
    if session_context.get("terms_to_avoid"):
        lines.append(f"Continue to avoid these terms: {session_context['terms_to_avoid']}")
    if session_context.get("institutional_rules"):
        lines.append(f"Institutional rules: {session_context['institutional_rules']}")
    lines += [
        "",
        "Apply the reviewer's instruction and return ONLY the revised JSON object.",
        "Preserve all fields. When applying a change, propagate it to ALL semantically related fields — for example, if location detail is added to description, also update places; if a person is identified in description, also update people; if a date is clarified, also update dates.",
        "Return ONLY the JSON object — no markdown fences, no explanation.",
    ]
    return "\n".join(lines)


def _parse_json_response(raw: str) -> dict:
    """Strip markdown fences and parse JSON, with a graceful fallback."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        log.warning("Could not parse VLM response as JSON; returning raw text in description.")
        return {"description": raw, "uncertainty_notes": "VLM response was not valid JSON."}


# ── Minimal prompt builders ───────────────────────────────────────────────────

def _build_minimal_generate_prompt(session_context: dict) -> str:
    ctx = session_context
    field_list = "\n".join(
        f'  "{f["key"]}": "<value or empty string>"'
        for f in METADATA_FIELDS
    )
    lines = [
        "You are a library metadata specialist. Examine this photograph and return ONLY a valid JSON object with these keys:",
        "{",
        field_list,
        "}",
        "",
    ]
    if ctx.get("collection_name"):
        lines.append(f"Collection: {ctx['collection_name']}")
    if ctx.get("known_locations"):
        lines.append(f"Known locations: {ctx['known_locations']}")
    if ctx.get("known_date_range"):
        lines.append(f"Known date range: {ctx['known_date_range']}")
    if ctx.get("known_people_orgs"):
        lines.append(f"Known people/organisations: {ctx['known_people_orgs']}")
    lines.append("")
    lines.append("Return ONLY the JSON object — no markdown fences, no explanation.")
    return "\n".join(lines)


def _build_minimal_verso_prompt(session_context: dict) -> str:
    ctx = session_context
    field_list = "\n".join(
        f'  "{f["key"]}": "<value or empty string>"'
        for f in METADATA_FIELDS
    )
    lines = [
        "You are a library metadata specialist. This is the VERSO (back side) of a photograph. Return ONLY a valid JSON object with these keys:",
        "{",
        field_list,
        "}",
        "",
    ]
    if ctx.get("collection_name"):
        lines.append(f"Collection: {ctx['collection_name']}")
    if ctx.get("recto_title"):
        lines.append(f"Front side title: \"{ctx['recto_title']}\"")
    if ctx.get("recto_description"):
        lines.append(f"Front side description: {ctx['recto_description']}")
    lines.append("")
    lines.append("Return ONLY the JSON object — no markdown fences, no explanation.")
    return "\n".join(lines)


def _pick_builder(session_context: dict):
    from app.config import PROMPT_STYLE
    is_verso = session_context.get("is_verso")
    if PROMPT_STYLE == "minimal":
        return _build_minimal_verso_prompt if is_verso else _build_minimal_generate_prompt
    return _build_verso_prompt if is_verso else _build_generate_prompt


# ── Mock backend (no model required) ─────────────────────────────────────────

def _mock_generate(image_path: str, session_context: dict) -> dict:
    fname = Path(image_path).stem
    return {
        "title": f"[MOCK] {fname}",
        "description": "A placeholder description generated by the mock backend. Replace with a real VLM.",
        "visible_text": "",
        "subjects": ["placeholder", "mock"],
        "people": [],
        "places": [],
        "dates": "",
        "objects": ["camera"],
        "uncertainty_notes": "This is a mock draft. Run with a real VLM model.",
        "reviewer_notes": "",
    }


def _mock_revise(image_path: str, current_metadata: dict, feedback: str, session_context: dict) -> dict:
    revised = dict(current_metadata)
    revised["reviewer_notes"] = f"[MOCK revision] Feedback received: {feedback}"
    revised["uncertainty_notes"] = "(Mock: revisions not applied — swap in a real VLM.)"
    return revised


# ── Qwen-VL backend ───────────────────────────────────────────────────────────

_qwen_model = None
_qwen_processor = None


def _load_qwen():
    global _qwen_model, _qwen_processor
    if _qwen_model is not None:
        return _qwen_model, _qwen_processor

    from app.config import QWEN_MODEL_ID, QWEN_DEVICE
    log.info("Loading Qwen-VL model: %s on %s", QWEN_MODEL_ID, QWEN_DEVICE)

    try:
        from transformers import AutoProcessor, Qwen2VLForConditionalGeneration
        import torch

        _qwen_processor = AutoProcessor.from_pretrained(QWEN_MODEL_ID, trust_remote_code=True)
        _qwen_model = Qwen2VLForConditionalGeneration.from_pretrained(
            QWEN_MODEL_ID,
            torch_dtype=torch.float16 if QWEN_DEVICE == "cuda" else torch.float32,
            device_map=QWEN_DEVICE,
            trust_remote_code=True,
        )
        _qwen_model.eval()
        log.info("Qwen-VL model loaded.")
    except ImportError as e:
        raise RuntimeError(
            "transformers / torch not installed or Qwen2VL not available. "
            "Install requirements or set MODEL_BACKEND=mock."
        ) from e

    return _qwen_model, _qwen_processor


def _qwen_infer(image_path: str, text_prompt: str) -> str:
    import torch
    from PIL import Image as PILImage

    model, processor = _load_qwen()

    image = PILImage.open(image_path).convert("RGB")
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": text_prompt},
            ],
        }
    ]
    # Apply chat template
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = processor(text=[text], images=[image], return_tensors="pt")
    device = next(model.parameters()).device
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        output_ids = model.generate(**inputs, max_new_tokens=1024, temperature=0, do_sample=False)
    # Decode only the new tokens
    generated = output_ids[:, inputs["input_ids"].shape[1]:]
    result = processor.batch_decode(generated, skip_special_tokens=True)[0]
    return result


def _qwen_generate(image_paths: list, session_context: dict) -> dict:
    builder = _pick_builder(session_context)
    raw = _qwen_infer(image_paths[0], builder(session_context))
    return _parse_json_response(raw)


def _qwen_revise(image_paths: list, current_metadata: dict, feedback: str, session_context: dict) -> dict:
    prompt = _build_revise_prompt(current_metadata, feedback, session_context)
    raw = _qwen_infer(image_paths[0], prompt)
    return _parse_json_response(raw)


# ── Ollama backend ────────────────────────────────────────────────────────────

def _encode_image(image_path: str, max_px: int, quality: int) -> str:
    import base64, io
    from PIL import Image as PILImage, ImageOps
    img = PILImage.open(image_path).convert("RGB")
    img = ImageOps.exif_transpose(img)
    img.thumbnail((max_px, max_px), PILImage.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode()


MAX_PAGES = 8        # vllm caps itself at 2 in _vllm_infer


def _multipage_prefix(n: int) -> str:
    if n <= 1:
        return ""
    return (
        f"This item has {n} pages and may be a folio, folder, or envelope containing multiple documents "
        f"(photographs, letters, notes, or other materials). "
        "Examine ALL pages carefully. Your description should describe the item as a whole — "
        "what it contains, not just the first page. If it contains a photograph AND a letter, describe both. "
        "Transcribe any visible text from letters or notes verbatim in visible_text. "
        "Use people, dates, and subjects drawn from ALL pages, not just the first.\n\n"
    )


def _ollama_infer(image_paths: list, text_prompt: str) -> str:
    import urllib.request
    import os
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=False)
    from app.config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_IMAGE_MAX_PX, OLLAMA_IMAGE_QUALITY
    OLLAMA_TOKEN = os.getenv("OLLAMA_TOKEN", "")

    pages = image_paths[:MAX_PAGES]
    images = [_encode_image(p, OLLAMA_IMAGE_MAX_PX, OLLAMA_IMAGE_QUALITY) for p in pages]
    prompt = _multipage_prefix(len(image_paths)) + text_prompt

    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "images": images,
        "stream": False,
        "options": {"temperature": 0},
    }).encode()

    headers = {"Content-Type": "application/json"}
    if OLLAMA_TOKEN:
        headers["Authorization"] = f"Bearer {OLLAMA_TOKEN}"

    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/generate",
        data=payload,
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        data = json.loads(resp.read())
    return data.get("response", "")


def _ollama_generate(image_paths: list, session_context: dict) -> dict:
    builder = _pick_builder(session_context)
    raw = _ollama_infer(image_paths, builder(session_context))
    return _parse_json_response(raw)


def _ollama_revise(image_paths: list, current_metadata: dict, feedback: str, session_context: dict) -> dict:
    prompt = _build_revise_prompt(current_metadata, feedback, session_context)
    raw = _ollama_infer(image_paths, prompt)
    return _parse_json_response(raw)


# ── vLLM backend (OpenAI-compatible) ─────────────────────────────────────────

def _vllm_infer(image_paths: list, text_prompt: str, max_px: int = None) -> str:
    """Transport lives in digtk.vllm_client (retries, maintenance-window pause,
    <think> stripping); this wrapper bridges MGA config and sizes the images."""
    import os
    from dotenv import load_dotenv
    from pathlib import Path
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=False)
    from app.config import (VLLM_BASE_URL, VLLM_MODEL, VLLM_IMAGE_MAX_PX,
                            OLLAMA_IMAGE_QUALITY, VLLM_READ_TIMEOUT, VLLM_RETRIES,
                            MAINT_PAUSE_START, MAINT_PAUSE_END)
    from digtk import config as dtk_config, raster, vllm_client

    base = VLLM_BASE_URL.rstrip("/")
    if not (base.endswith("/api") or base.endswith("/v1")):
        base += "/v1"  # bare host configured (old cyberdyne style)
    dtk_config.VLLM_BASE_URL = base
    dtk_config.VLLM_MODEL = VLLM_MODEL
    dtk_config.VLLM_API_KEY = os.getenv("VLLM_TOKEN", "") or os.getenv("OLLAMA_TOKEN", "")
    dtk_config.VLLM_READ_TIMEOUT = VLLM_READ_TIMEOUT
    dtk_config.VLLM_RETRIES = VLLM_RETRIES
    dtk_config.MAINT_PAUSE_START = MAINT_PAUSE_START
    dtk_config.MAINT_PAUSE_END = MAINT_PAUSE_END

    px = max_px or VLLM_IMAGE_MAX_PX
    pages = image_paths[:2]  # vllm server limit per request
    image_bytes = [raster.to_jpeg(p, max_px=px, quality=OLLAMA_IMAGE_QUALITY)
                   for p in pages]
    prompt = _multipage_prefix(len(image_paths)) + text_prompt
    return vllm_client.chat(image_bytes, prompt, max_tokens=8192, temperature=0.0)


def _vllm_generate(image_paths: list, session_context: dict) -> dict:
    builder = _pick_builder(session_context)
    raw = _vllm_infer(image_paths, builder(session_context))
    return _parse_json_response(raw)


def _vllm_revise(image_paths: list, current_metadata: dict, feedback: str, session_context: dict) -> dict:
    prompt = _build_revise_prompt(current_metadata, feedback, session_context)
    raw = _vllm_infer(image_paths, prompt)
    return _parse_json_response(raw)


# ── Claude API backend ────────────────────────────────────────────────────────

def _claude_infer(image_paths: list, text_prompt: str) -> str:
    import anthropic
    from app.config import ANTHROPIC_API_KEY, CLAUDE_MODEL, OLLAMA_IMAGE_MAX_PX, OLLAMA_IMAGE_QUALITY

    image_blocks = [
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _encode_image(p, OLLAMA_IMAGE_MAX_PX, OLLAMA_IMAGE_QUALITY)}}
        for p in image_paths
    ]
    prompt = _multipage_prefix(len(image_paths)) + text_prompt

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        temperature=0,
        messages=[{"role": "user", "content": image_blocks + [{"type": "text", "text": prompt}]}],
    )
    return message.content[0].text


def _claude_generate(image_paths: list, session_context: dict) -> dict:
    builder = _pick_builder(session_context)
    raw = _claude_infer(image_paths, builder(session_context))
    return _parse_json_response(raw)


def _claude_revise(image_paths: list, current_metadata: dict, feedback: str, session_context: dict) -> dict:
    prompt = _build_revise_prompt(current_metadata, feedback, session_context)
    raw = _claude_infer(image_paths, prompt)
    return _parse_json_response(raw)


# ── Public interface ──────────────────────────────────────────────────────────

def _infer(image_paths: list, prompt: str, max_px: int = None) -> str:
    """Backend-agnostic vision call (used by classify + OCR)."""
    backend = MODEL_BACKEND
    if backend == "vllm":
        return _vllm_infer(image_paths, prompt, max_px=max_px)
    elif backend == "ollama":
        return _ollama_infer(image_paths, prompt)
    elif backend == "claude":
        return _claude_infer(image_paths, prompt)
    elif backend == "qwen_vl":
        return _qwen_infer(image_paths[0], prompt)
    return ""


def _backend_generate(image_paths: list, session_context: dict) -> dict:
    backend = MODEL_BACKEND
    if backend == "qwen_vl":
        return _qwen_generate(image_paths, session_context)
    elif backend == "ollama":
        return _ollama_generate(image_paths, session_context)
    elif backend == "vllm":
        return _vllm_generate(image_paths, session_context)
    elif backend == "claude":
        return _claude_generate(image_paths, session_context)
    elif backend == "mock":
        return _mock_generate(image_paths[0], session_context)
    else:
        raise ValueError(f"Unknown MODEL_BACKEND: {backend!r}. Choose qwen_vl, ollama, vllm, claude, or mock.")


def generate_metadata(image_paths: "str | list", session_context: dict) -> dict:
    """Generate draft metadata. Auto-detects textual documents and routes them to a
    full-OCR + searchable-PDF branch; photos get the usual description path."""
    if isinstance(image_paths, str):
        image_paths = [image_paths]
    backend = MODEL_BACKEND
    log.info("generate_metadata: backend=%s pages=%d", backend, len(image_paths))

    from app.config import DOC_DETECT, DOC_OCR_MAX_PX
    if DOC_DETECT and backend != "mock":
        try:
            from app.models import documents
            dtype = documents.classify_doc_type(image_paths, _infer)
            log.info("classified as %s", dtype)
            if dtype == "document":
                def _ocr_infer(ips, pr):
                    return _infer(ips, pr, max_px=DOC_OCR_MAX_PX)
                return documents.process_document(
                    image_paths, session_context, _infer, _ocr_infer, _parse_json_response)
        except Exception as e:  # noqa: BLE001 - never let doc routing break generation
            log.warning("doc detection/branch failed (%s); using photo path", e)

    md = _backend_generate(image_paths, session_context)
    if isinstance(md, dict):
        md["doc_type"] = "photo"          # authoritative (photo branch)
        md.pop("full_ocr_text", None)     # document-only field
    return md


def revise_metadata(
    image_paths: "str | list",
    current_metadata: dict,
    feedback: str,
    session_context: dict,
) -> dict:
    """Revise existing metadata based on reviewer feedback using the local VLM."""
    if isinstance(image_paths, str):
        image_paths = [image_paths]
    backend = MODEL_BACKEND
    log.info("revise_metadata: backend=%s feedback=%r", backend, feedback[:80])
    if backend == "qwen_vl":
        return _qwen_revise(image_paths, current_metadata, feedback, session_context)
    elif backend == "ollama":
        return _ollama_revise(image_paths, current_metadata, feedback, session_context)
    elif backend == "vllm":
        return _vllm_revise(image_paths, current_metadata, feedback, session_context)
    elif backend == "claude":
        return _claude_revise(image_paths, current_metadata, feedback, session_context)
    elif backend == "mock":
        return _mock_revise(image_paths[0], current_metadata, feedback, session_context)
    else:
        raise ValueError(f"Unknown MODEL_BACKEND: {backend!r}.")
