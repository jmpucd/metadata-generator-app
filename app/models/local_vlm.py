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
        "Analyze a photo.",
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
        "- If you are uncertain about any value, note it in uncertainty_notes.",
        "- reviewer_notes: add any archival observations about approximate date, context, or significance that a cataloguer would find useful.",
        "- Return ONLY the JSON object — no markdown fences, no explanation.",
    ]
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
        "Preserve all fields; only change those affected by the instruction.",
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


def _qwen_generate(image_path: str, session_context: dict) -> dict:
    prompt = _build_generate_prompt(session_context)
    raw = _qwen_infer(image_path, prompt)
    return _parse_json_response(raw)


def _qwen_revise(image_path: str, current_metadata: dict, feedback: str, session_context: dict) -> dict:
    prompt = _build_revise_prompt(current_metadata, feedback, session_context)
    raw = _qwen_infer(image_path, prompt)
    return _parse_json_response(raw)


# ── Ollama backend ────────────────────────────────────────────────────────────

def _ollama_infer(image_path: str, text_prompt: str) -> str:
    import base64
    import urllib.request

    import os
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=False)
    from app.config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_IMAGE_MAX_PX, OLLAMA_IMAGE_QUALITY
    OLLAMA_TOKEN = os.getenv("OLLAMA_TOKEN", "")
    from PIL import Image as PILImage, ImageOps
    import io

    img = PILImage.open(image_path).convert("RGB")
    img = ImageOps.exif_transpose(img)
    img.thumbnail((OLLAMA_IMAGE_MAX_PX, OLLAMA_IMAGE_MAX_PX), PILImage.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=OLLAMA_IMAGE_QUALITY)
    b64 = base64.b64encode(buf.getvalue()).decode()

    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": text_prompt,
        "images": [b64],
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


def _ollama_generate(image_path: str, session_context: dict) -> dict:
    prompt = _build_generate_prompt(session_context)
    raw = _ollama_infer(image_path, prompt)
    return _parse_json_response(raw)


def _ollama_revise(image_path: str, current_metadata: dict, feedback: str, session_context: dict) -> dict:
    prompt = _build_revise_prompt(current_metadata, feedback, session_context)
    raw = _ollama_infer(image_path, prompt)
    return _parse_json_response(raw)


# ── Claude API backend ────────────────────────────────────────────────────────

def _claude_infer(image_path: str, text_prompt: str) -> str:
    import base64
    import io
    import anthropic
    from PIL import Image as PILImage, ImageOps
    from app.config import ANTHROPIC_API_KEY, CLAUDE_MODEL, OLLAMA_IMAGE_MAX_PX, OLLAMA_IMAGE_QUALITY

    img = PILImage.open(image_path).convert("RGB")
    img = ImageOps.exif_transpose(img)
    img.thumbnail((OLLAMA_IMAGE_MAX_PX, OLLAMA_IMAGE_MAX_PX), PILImage.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=OLLAMA_IMAGE_QUALITY)
    b64 = base64.standard_b64encode(buf.getvalue()).decode()

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        temperature=0,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                    {"type": "text", "text": text_prompt},
                ],
            }
        ],
    )
    return message.content[0].text


def _claude_generate(image_path: str, session_context: dict) -> dict:
    prompt = _build_generate_prompt(session_context)
    raw = _claude_infer(image_path, prompt)
    return _parse_json_response(raw)


def _claude_revise(image_path: str, current_metadata: dict, feedback: str, session_context: dict) -> dict:
    prompt = _build_revise_prompt(current_metadata, feedback, session_context)
    raw = _claude_infer(image_path, prompt)
    return _parse_json_response(raw)


# ── Public interface ──────────────────────────────────────────────────────────

def generate_metadata(image_path: str, session_context: dict) -> dict:
    """Generate draft metadata for an image using the configured local VLM."""
    backend = MODEL_BACKEND
    log.info("generate_metadata: backend=%s path=%s", backend, image_path)
    if backend == "qwen_vl":
        return _qwen_generate(image_path, session_context)
    elif backend == "ollama":
        return _ollama_generate(image_path, session_context)
    elif backend == "claude":
        return _claude_generate(image_path, session_context)
    elif backend == "mock":
        return _mock_generate(image_path, session_context)
    else:
        raise ValueError(f"Unknown MODEL_BACKEND: {backend!r}. Choose qwen_vl, ollama, claude, or mock.")


def revise_metadata(
    image_path: str,
    current_metadata: dict,
    feedback: str,
    session_context: dict,
) -> dict:
    """Revise existing metadata based on reviewer feedback using the local VLM."""
    backend = MODEL_BACKEND
    log.info("revise_metadata: backend=%s feedback=%r", backend, feedback[:80])
    if backend == "qwen_vl":
        return _qwen_revise(image_path, current_metadata, feedback, session_context)
    elif backend == "ollama":
        return _ollama_revise(image_path, current_metadata, feedback, session_context)
    elif backend == "claude":
        return _claude_revise(image_path, current_metadata, feedback, session_context)
    elif backend == "mock":
        return _mock_revise(image_path, current_metadata, feedback, session_context)
    else:
        raise ValueError(f"Unknown MODEL_BACKEND: {backend!r}.")
