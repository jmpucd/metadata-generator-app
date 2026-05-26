#!/usr/bin/env bash
# run_pipeline.sh — Metadata Generator App: automated pipeline steps
#
# Covers: ingest → generate (VLM drafts) → export
# Human review happens in the web UI between generate and export.
#
# Usage:
#   ./run_pipeline.sh <images_dir> "<collection_name>" [json|csv|xmp|all]
#
# Examples:
#   ./run_pipeline.sh images/incoming "Spring 2025 Photos" json
#   ./run_pipeline.sh /data/scans "Album 1" all
#
# Environment:
#   Copy .env.example to .env and set MODEL_BACKEND, OLLAMA_TOKEN, etc.
#   before running.

set -euo pipefail

IMAGES_DIR="${1:?Error: images_dir required. Usage: $0 <images_dir> <collection_name> [export_format]}"
COLLECTION="${2:?Error: collection_name required.}"
EXPORT_FORMAT="${3:-json}"
APP_DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$APP_DIR"

# Activate virtualenv
if [[ ! -f .venv/bin/activate ]]; then
  echo "ERROR: .venv not found. Run: python -m venv .venv && pip install -e ." >&2
  exit 1
fi
source .venv/bin/activate

# Load .env if present
if [[ -f .env ]]; then
  set -a; source .env; set +a
fi

echo ""
echo "================================================"
echo " Metadata Generator Pipeline"
echo " Collection : $COLLECTION"
echo " Images dir : $IMAGES_DIR"
echo " Export fmt : $EXPORT_FORMAT"
echo " Model      : ${MODEL_BACKEND:-ollama}"
echo "================================================"
echo ""

# ----- STEP 1: INGEST -----
echo "=== [1/3] INGEST ==="
echo "Scanning $IMAGES_DIR and registering images in database..."
python -m app.cli ingest "$IMAGES_DIR" --collection "$COLLECTION"
echo ""

# ----- STEP 2: GENERATE (VLM) -----
echo "=== [2/3] GENERATE (VLM drafts) ==="
echo "Sending images to VLM (${MODEL_BACKEND:-ollama}). This may take a while..."
python -m app.cli generate --collection "$COLLECTION"
echo ""

# ----- STEP 3: EXPORT -----
echo "=== [3/3] EXPORT ($EXPORT_FORMAT) ==="
if [[ "$EXPORT_FORMAT" == "all" ]]; then
  python -m app.cli export --format json
  python -m app.cli export --format csv
  python -m app.cli export --format xmp
else
  python -m app.cli export --format "$EXPORT_FORMAT"
fi
echo ""

echo "================================================"
echo " Done. Output written to: data/exports/"
echo ""
echo " Next steps:"
echo "  - Launch the review UI to approve/edit drafts:"
echo "      Terminal 1: uvicorn api.main:app --port 8000 --reload"
echo "      Terminal 2: cd ui && npm run dev"
echo "      Browser   : http://localhost:5173"
echo ""
echo "  - Once items are approved, re-run export:"
echo "      python -m app.cli export --format $EXPORT_FORMAT"
echo "================================================"
