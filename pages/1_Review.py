"""
pages/1_Review.py — the core review interface.
Image full-width on top, metadata form below.
"""
from __future__ import annotations

import datetime
import json

import streamlit as st

from app.config import METADATA_FIELDS, REVIEW_STATUSES
from app.db.crud import (
    get_metadata,
    get_revision_history,
    list_collections,
    list_images,
    set_review_status,
    snapshot_revision,
    status_counts,
    upsert_metadata,
)
from app.db.schema import create_tables, get_session
from app.models.local_vlm import revise_metadata
from app.utils.image_utils import make_thumbnail_bytes

create_tables()

# ── Page config ───────────────────────────────────────────────────────────────
st.header("🔍 Review")

db = get_session()
collections = list_collections(db)

if not collections:
    st.warning("No collections found. Go to **Session Setup** to create one first.")
    st.stop()

# ── Sidebar: collection + filter ──────────────────────────────────────────────
with st.sidebar:
    st.subheader("Collection")
    col_names = [c.name for c in collections]
    selected_col_name = st.selectbox("Collection", col_names, label_visibility="collapsed")
    selected_col = next(c for c in collections if c.name == selected_col_name)

    st.subheader("Filter by status")
    status_filter = st.selectbox(
        "Status",
        ["all"] + REVIEW_STATUSES,
        label_visibility="collapsed",
    )

    counts = status_counts(db, collection_id=selected_col.id)
    st.caption("Status counts:")
    for s in REVIEW_STATUSES:
        st.caption(f"  {s}: {counts.get(s, 0)}")

# ── Load image list ───────────────────────────────────────────────────────────
images = list_images(
    db,
    collection_id=selected_col.id,
    status=None if status_filter == "all" else status_filter,
)

if not images:
    st.info("No images found for this collection / filter.")
    st.caption("Use `python -m app.cli ingest /path/to/folder --collection …` to add images.")
    st.stop()

# ── Image navigation ──────────────────────────────────────────────────────────
if "img_index" not in st.session_state:
    st.session_state.img_index = 0

st.session_state.img_index = min(st.session_state.img_index, len(images) - 1)

nav_col1, nav_col2, nav_col3 = st.columns([1, 6, 1])
with nav_col1:
    if st.button("◀ Prev") and st.session_state.img_index > 0:
        st.session_state.img_index -= 1
        st.rerun()
with nav_col3:
    if st.button("Next ▶") and st.session_state.img_index < len(images) - 1:
        st.session_state.img_index += 1
        st.rerun()
with nav_col2:
    jump = st.number_input(
        f"Image {st.session_state.img_index + 1} of {len(images)}",
        min_value=1, max_value=len(images),
        value=st.session_state.img_index + 1,
        step=1,
        label_visibility="collapsed",
    )
    if jump - 1 != st.session_state.img_index:
        st.session_state.img_index = jump - 1
        st.rerun()

current_image = images[st.session_state.img_index]
rec = get_metadata(db, current_image.id)

# Mark as in_progress when opened
if rec and rec.review_status == "needs_review":
    set_review_status(db, current_image.id, "in_progress")

# ── Image (full width) ────────────────────────────────────────────────────────
st.subheader(current_image.filename)
try:
    thumb = make_thumbnail_bytes(current_image.filepath)
    st.image(thumb, use_container_width=True)
except Exception as e:
    st.error(f"Could not load image: {e}")

st.caption(f"`{current_image.filepath}`")

# ── Status + quick actions ────────────────────────────────────────────────────
status = rec.review_status if rec else "needs_review"
badge_colors = {
    "needs_review": "🟡",
    "in_progress":  "🔵",
    "revised":      "🟣",
    "approved":     "🟢",
    "flagged":      "🔴",
}
st.markdown(f"**Status:** {badge_colors.get(status, '⚪')} `{status}`")

qc1, qc2, qc3 = st.columns([1, 1, 2])
with qc1:
    if st.button("✅ Approve", use_container_width=True):
        snapshot_revision(db, current_image.id, "approved", revised_by="reviewer")
        set_review_status(db, current_image.id, "approved")
        st.success("Approved!")
        st.rerun()
with qc2:
    if st.button("🚩 Flag", use_container_width=True):
        set_review_status(db, current_image.id, "flagged")
        st.rerun()
with qc3:
    new_status = st.selectbox(
        "Set status",
        REVIEW_STATUSES,
        index=REVIEW_STATUSES.index(status),
        label_visibility="collapsed",
    )
    if new_status != status:
        set_review_status(db, current_image.id, new_status)
        st.rerun()

st.divider()

# ── Metadata form (full width) ────────────────────────────────────────────────
st.subheader("Metadata")

form_values: dict = {}
with st.form(key=f"metadata_form_{current_image.id}"):
    for field in METADATA_FIELDS:
        key = field["key"]
        label = field["label"]
        ftype = field["type"]

        if ftype == "textarea":
            current_val = getattr(rec, key, "") or "" if rec else ""
            form_values[key] = st.text_area(label, value=current_val, height=100)
        elif ftype == "text":
            current_val = getattr(rec, key, "") or "" if rec else ""
            form_values[key] = st.text_input(label, value=current_val)
        elif ftype == "tags":
            tag_list = rec.get_tags(key) if rec else []
            tag_str = ", ".join(tag_list)
            raw = st.text_input(label + " (comma-separated)", value=tag_str)
            form_values[key] = [t.strip() for t in raw.split(",") if t.strip()]

    save_col, _ = st.columns([1, 3])
    with save_col:
        saved = st.form_submit_button("💾 Save edits", type="primary")

if saved:
    snapshot_revision(db, current_image.id, "human_edit", revised_by="reviewer")
    upsert_metadata(db, current_image.id, form_values)
    st.success("Metadata saved.")
    st.rerun()

# ── Model revision panel ──────────────────────────────────────────────────────
st.divider()
st.subheader("🤖 Ask model to revise")

preset_feedback = st.selectbox(
    "Quick presets",
    [
        "— choose a preset or type your own below —",
        "Make this description more neutral.",
        "Do not infer the event — describe only what is visible.",
        "Use simpler, public-facing language.",
        "Remove any terms that are potentially offensive or outdated.",
        "Expand the description with more visual detail.",
        "Shorten the description to two sentences.",
    ],
)
feedback_text = st.text_area(
    "Feedback / instruction to model",
    value="" if preset_feedback.startswith("—") else preset_feedback,
    placeholder="e.g. 'This is not a tractor, it is a combine harvester.'",
    height=80,
)

if st.button("🔄 Send to model", disabled=not feedback_text.strip()):
    if not rec:
        st.error("No metadata record yet. Save a draft first.")
    else:
        with st.spinner("Asking model to revise…"):
            current_meta = rec.to_dict()
            try:
                revised = revise_metadata(
                    image_path=current_image.filepath,
                    current_metadata=current_meta,
                    feedback=feedback_text,
                    session_context=selected_col.session_context(),
                )
                snapshot_revision(db, current_image.id, "model_revision", feedback=feedback_text)
                upsert_metadata(db, current_image.id, revised)
                set_review_status(db, current_image.id, "revised")
                st.success("Model revision applied. Review the changes above.")
                st.rerun()
            except Exception as e:
                st.error(f"Model error: {e}")

# ── Revision history ──────────────────────────────────────────────────────────
history = get_revision_history(db, current_image.id)
if history:
    with st.expander(f"📜 Revision history ({len(history)} entries)", expanded=False):
        for entry in history:
            ts = entry.revised_at.strftime("%Y-%m-%d %H:%M")
            st.markdown(f"**{ts}** · `{entry.revision_type}` · by *{entry.revised_by}*")
            if entry.feedback_given:
                st.caption(f"Feedback: {entry.feedback_given}")
            snap = json.loads(entry.metadata_snapshot)
            with st.expander("Snapshot", expanded=False):
                st.json(snap)
