"""
app/prompt_packs.py
===================
Reusable prompt modules ("packs").

A pack is a markdown file in `prompts/packs/` holding rules that are true for a *kind* of
material rather than for one collection — CJK text handling, interior/foodways description,
correspondence conventions. Collections opt in by listing pack names in
`Collection.prompt_packs`; the bodies are appended to the prompt after the collection
context.

The base prompt keeps what is true for every collection (the JSON contract, uncertainty
conventions, the general foreign-language rule). Packs carry the material-specific
examples, so a collection only pays for the rules it needs.

File format — `---` fenced key/value header, then the rule body:

    ---
    name: language-cjk
    description: shown in the UI and `python -m app.cli packs`
    applies_to: photo, verso, document
    tess_lang: eng+chi_tra+chi_sim
    ---

    - one rule per line, phrased as an instruction to the model

`applies_to` limits a pack to certain prompt paths (default: all three). `tess_lang` is
optional and merges into the Tesseract languages used to build the searchable PDF text
layer, so a language pack fixes both the prompt and the word-box pass.

Nothing here is allowed to break generation: an unknown pack name or an unreadable file
logs a warning and is skipped.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

log = logging.getLogger(__name__)

KINDS = ("photo", "verso", "document")


def _parse_pack(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    meta: dict[str, str] = {}
    body = raw
    if raw.lstrip().startswith("---"):
        parts = raw.lstrip().split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().splitlines():
                if ":" in line:
                    key, val = line.split(":", 1)
                    meta[key.strip().lower()] = val.strip()
            body = parts[2]

    applies = [k.strip().lower() for k in meta.get("applies_to", "").split(",") if k.strip()]
    unknown = [k for k in applies if k not in KINDS]
    if unknown:
        log.warning("pack %s: ignoring unknown applies_to value(s) %s", path.name, unknown)
    applies = [k for k in applies if k in KINDS] or list(KINDS)

    return {
        "name": meta.get("name") or path.stem,
        "description": meta.get("description", ""),
        "applies_to": applies,
        "tess_lang": meta.get("tess_lang", ""),
        "body": body.strip(),
        "path": str(path),
    }


@lru_cache(maxsize=1)
def _packs() -> dict[str, dict]:
    """All packs on disk, keyed by name. Cached — call `reload()` after editing files."""
    from app.config import PACKS_DIR

    found: dict[str, dict] = {}
    directory = Path(PACKS_DIR)
    if not directory.is_dir():
        log.warning("prompt pack directory not found: %s", directory)
        return found
    for path in sorted(directory.glob("*.md")):
        try:
            pack = _parse_pack(path)
        except Exception as e:  # noqa: BLE001 — a bad pack must not break generation
            log.warning("could not read prompt pack %s: %s", path.name, e)
            continue
        if not pack["body"]:
            log.warning("prompt pack %s has an empty body; skipping", path.name)
            continue
        if pack["name"] in found:
            log.warning("duplicate prompt pack name %r (%s); keeping the first",
                        pack["name"], path.name)
            continue
        found[pack["name"]] = pack
    return found


def reload() -> None:
    """Drop the cache so edited pack files are picked up without a restart."""
    _packs.cache_clear()


def list_packs() -> list[dict]:
    return list(_packs().values())


def parse_names(value) -> list[str]:
    """Accept a comma/newline-separated string or a list; return clean names, in order."""
    if not value:
        return []
    if isinstance(value, str):
        value = value.replace("\n", ",").split(",")
    seen, names = set(), []
    for raw in value:
        name = str(raw).strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def resolve(value, kind: str = "photo") -> list[dict]:
    """Look up the named packs that apply to `kind`, preserving the collection's order."""
    available = _packs()
    out = []
    for name in parse_names(value):
        pack = available.get(name)
        if pack is None:
            log.warning("unknown prompt pack %r — skipping (available: %s)",
                        name, ", ".join(sorted(available)) or "none")
            continue
        if kind in pack["applies_to"]:
            out.append(pack)
    return out


def pack_lines(value, kind: str = "photo") -> list[str]:
    """Prompt lines contributed by the collection's packs, or [] if there are none."""
    packs = resolve(value, kind)
    if not packs:
        return []
    lines = ["", "Additional rules for this collection:"]
    for pack in packs:
        lines.append(pack["body"])
    return lines


def tess_lang_for(value, default: str = "eng") -> str:
    """Merge the default Tesseract languages with any contributed by packs."""
    langs: list[str] = []
    for source in [default] + [p["tess_lang"] for p in resolve(value, "document")]:
        for lang in str(source or "").split("+"):
            lang = lang.strip()
            if lang and lang not in langs:
                langs.append(lang)
    return "+".join(langs) or "eng"
