"""
app/export/json_export.py
app/export/csv_export.py
app/export/xmp_export.py
All in one file for simplicity; split if they grow.
"""
from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

from app.config import EXPORTS_DIR


# ── Shared helpers ────────────────────────────────────────────────────────────

def _record_to_flat(item, rec) -> dict:
    """Flatten an (Item, MetadataRecord) pair into a plain dict."""
    d = rec.to_dict()
    for key in ("subjects", "people", "places", "objects"):
        val = d.get(key, [])
        if isinstance(val, list):
            d[key] = " | ".join(val)
    rep = item.pages[0] if item.pages else None
    d["item_key"] = item.item_key
    d["series"] = item.series or ""
    d["filename"] = rep.filename if rep else ""
    d["filepath"] = rep.filepath if rep else ""
    d["page_count"] = len(item.pages)
    return d


# ── JSON export ───────────────────────────────────────────────────────────────

def export_json(records: list, output_path: Path | None = None) -> Path:
    """Export approved records to a single JSON file."""
    if output_path is None:
        output_path = EXPORTS_DIR / "approved_metadata.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = []
    for item, rec in records:
        entry = rec.to_dict()
        rep = item.pages[0] if item.pages else None
        entry["item_key"] = item.item_key
        entry["series"] = item.series or ""
        entry["filename"] = rep.filename if rep else ""
        entry["filepath"] = rep.filepath if rep else ""
        entry["page_count"] = len(item.pages)
        for key in ("subjects", "people", "places", "objects"):
            entry[key] = rec.get_tags(key)
        data.append(entry)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    return output_path


# ── CSV export ────────────────────────────────────────────────────────────────

def export_csv(records: list, output_path: Path | None = None) -> Path:
    """Export approved records to a CSV file."""
    if output_path is None:
        output_path = EXPORTS_DIR / "approved_metadata.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = [_record_to_flat(item, rec) for item, rec in records]
    if not rows:
        output_path.write_text("(no approved records)\n")
        return output_path

    fieldnames = list(rows[0].keys())
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return output_path


# ── XMP / IPTC sidecar export (via ExifTool) ─────────────────────────────────

def export_xmp(records: list, output_dir: Path | None = None) -> list[Path]:
    """
    Write XMP sidecar files (.xmp) next to each approved image using ExifTool.
    Requires ExifTool to be installed: https://exiftool.org/

    Returns a list of sidecar paths written.
    """
    if output_dir is None:
        output_dir = EXPORTS_DIR / "xmp_sidecars"
    output_dir.mkdir(parents=True, exist_ok=True)

    written = []
    for item, rec in records:
        rep = item.pages[0] if item.pages else None
        if not rep:
            continue
        img_path = Path(rep.filepath)
        sidecar_path = output_dir / (img_path.stem + ".xmp")

        tags = rec.get_tags
        args = [
            "exiftool",
            "-overwrite_original",
            f"-XMP:Title={rec.title or ''}",
            f"-XMP:Description={rec.description or ''}",
            f"-IPTC:Caption-Abstract={rec.description or ''}",
            f"-XMP:Date={rec.dates or ''}",
        ]
        for kw in rec.get_tags("subjects"):
            args.append(f"-XMP:Subject={kw}")
            args.append(f"-IPTC:Keywords={kw}")

        # Write to a copy in the sidecar dir; ExifTool operates on the source file
        # If you want pure sidecars without touching originals, use -o flag:
        args = [
            "exiftool",
            f"-Title={rec.title or ''}",
            f"-Description={rec.description or ''}",
            f"-Date={rec.dates or ''}",
        ]
        for kw in rec.get_tags("subjects"):
            args.append(f"-Keywords={kw}")

        # Output a .xmp sidecar
        args += ["-o", str(sidecar_path), str(img_path)]

        result = subprocess.run(args, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"ExifTool failed for {img_path.name}:\n{result.stderr}"
            )
        written.append(sidecar_path)

    return written
