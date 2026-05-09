"""
pages/1_Review.py — exhibition folio.
Object dominates. Annotations follow the image.
"""
from __future__ import annotations
import json
import streamlit as st

from app.config import REVIEW_STATUSES
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

_sys = "system-ui, -apple-system, 'Helvetica Neue', Helvetica, Arial, sans-serif"

# ── Page-specific editorial CSS ───────────────────────────────────────────────
st.markdown("""
<style>
/* ── Object first ── */
.block-container { padding-top: 0.4rem !important; }

/* ── Image: full presence, constrained only by viewport ── */
[data-testid="stImage"] { margin: 0 !important; }
[data-testid="stImage"] img {
    width: 100% !important;
    max-height: 78vh !important;
    min-height: 40vh !important;
    object-fit: contain !important;
    object-position: center !important;
    display: block !important;
}

/* ── Folio header strip ── */
.folio-id {
    display: flex;
    align-items: baseline;
    gap: 2.5rem;
    margin-bottom: 1rem;
}
.folio-id-col {
    font-size: 0.5rem;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: #D0D0D0;
    font-weight: 500;
}
.folio-id-file {
    font-family: "Courier New", Courier, monospace;
    font-size: 0.68rem;
    letter-spacing: 0.03em;
    color: #C4C4C4;
}

/* ── Left-gutter catalog index ── */
.folio-cat-num {
    font-family: "Courier New", Courier, monospace;
    font-size: 0.52rem;
    letter-spacing: 0.06em;
    color: #E2E2E2;
    line-height: 1.7;
    padding-top: 0.15rem;
    user-select: none;
}

/* ── Kill all form chrome ── */
[data-testid="stForm"] {
    border: none !important;
    padding: 0 !important;
    background: transparent !important;
}
[data-testid="stForm"] label { display: none !important; }

/* ── Title: editorial headline ── */
[data-testid="element-container"]:has(.fld-title) + [data-testid="element-container"] input {
    font-size: 1.15rem !important;
    font-weight: 300 !important;
    letter-spacing: -0.01em !important;
    color: #0E0E0E !important;
    line-height: 1.35 !important;
    padding-bottom: 0.8rem !important;
    border-bottom: 1px solid #EFEFEF !important;
}
[data-testid="element-container"]:has(.fld-title) + [data-testid="element-container"] input:focus {
    border-bottom-color: #C0C0C0 !important;
}

/* ── Description: body copy, constrained measure ── */
[data-testid="element-container"]:has(.fld-desc) + [data-testid="element-container"] .stTextArea {
    max-width: 72ch !important;
}
[data-testid="element-container"]:has(.fld-desc) + [data-testid="element-container"] textarea {
    font-size: 0.875rem !important;
    font-weight: 400 !important;
    color: #1C1C1C !important;
    line-height: 1.82 !important;
    padding-bottom: 0.65rem !important;
    border-bottom: 1px solid #EFEFEF !important;
}
[data-testid="element-container"]:has(.fld-desc) + [data-testid="element-container"] textarea:focus {
    border-bottom-color: #C0C0C0 !important;
}

/* ── Subjects: catalog tag fragments ── */
[data-testid="element-container"]:has(.fld-subj) + [data-testid="element-container"] input {
    font-size: 0.6rem !important;
    letter-spacing: 0.14em !important;
    color: #AAAAAA !important;
    text-transform: uppercase !important;
    border-bottom-color: transparent !important;
    padding-bottom: 0.5rem !important;
}
[data-testid="element-container"]:has(.fld-subj) + [data-testid="element-container"] input:focus {
    border-bottom-color: #EBEBEB !important;
}

/* ── Anno labels: barely-there catalog notation ── */
.anno-label {
    display: block;
    font-size: 0.47rem;
    font-weight: 600;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: #D6D6D6;
    margin-top: 2.2rem;
    margin-bottom: 0.1rem;
    line-height: 1;
}
.fld-title { margin-top: 0 !important; }

/* ── Expander within form: secondary nav fragment ── */
[data-testid="stForm"] [data-testid="stExpander"] summary {
    font-size: 0.48rem !important;
    letter-spacing: 0.14em !important;
    color: #D4D4D4 !important;
    text-transform: lowercase !important;
    padding: 1.2rem 0 0.4rem !important;
}
[data-testid="stForm"] [data-testid="stExpander"] summary:hover { color: #666 !important; }
[data-testid="stForm"] [data-testid="stExpander"] > div[data-testid="stExpanderDetails"] {
    padding: 0 !important;
    border: none !important;
}

/* ── Zero gap between form elements ── */
[data-testid="stForm"] [data-testid="stVerticalBlock"] { gap: 0 !important; }

/* ── Sidebar: quieter labels ── */
section[data-testid="stSidebar"] .stSelectbox label {
    font-size: 0.48rem !important;
    letter-spacing: 0.2em !important;
    text-transform: uppercase !important;
    color: #D4D4D4 !important;
    font-weight: 600 !important;
    margin-bottom: 0.2rem !important;
    display: block !important;
}

/* ── Nav buttons: typographic marks only ── */
.stButton > button {
    font-size: 0.55rem !important;
    letter-spacing: 0.12em !important;
    color: #D4D4D4 !important;
}
.stButton > button:hover { color: #111 !important; }
</style>
""", unsafe_allow_html=True)

# ── DB + collections ──────────────────────────────────────────────────────────
db = get_session()
collections = list_collections(db)

if not collections:
    st.warning("No collections found. Go to Session Setup first.")
    st.stop()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    col_names = [c.name for c in collections]
    selected_col_name = st.selectbox("Collection", col_names)
    selected_col = next(c for c in collections if c.name == selected_col_name)

    status_filter = st.selectbox("Filter", ["all"] + REVIEW_STATUSES)

    counts = status_counts(db, collection_id=selected_col.id)
    rows = "".join(
        f'<div style="display:flex;justify-content:space-between;align-items:baseline;'
        f'padding:4px 0;border-top:1px solid #F8F8F8;">'
        f'<span style="font-size:0.48rem;letter-spacing:0.14em;text-transform:uppercase;'
        f'color:#D4D4D4;font-family:{_sys};font-weight:500;">{s.replace("_", " ")}</span>'
        f'<span style="font-size:0.55rem;color:#BBBBBB;font-variant-numeric:tabular-nums;'
        f'font-family:\'Courier New\',monospace;letter-spacing:0.04em;">'
        f'{counts.get(s, 0):03d}</span>'
        f'</div>'
        for s in REVIEW_STATUSES
    )
    st.markdown(
        f'<div style="margin-top:0.75rem;">{rows}</div>',
        unsafe_allow_html=True,
    )

# ── Image list ────────────────────────────────────────────────────────────────
images = list_images(
    db,
    collection_id=selected_col.id,
    status=None if status_filter == "all" else status_filter,
)

if not images:
    st.info("No images match this filter.")
    st.stop()

if "img_index" not in st.session_state:
    st.session_state.img_index = 0
st.session_state.img_index = min(st.session_state.img_index, len(images) - 1)
idx = st.session_state.img_index

current_image = images[idx]
rec = get_metadata(db, current_image.id)

if rec and rec.review_status == "needs_review":
    set_review_status(db, current_image.id, "in_progress")

status = rec.review_status if rec else "needs_review"

def _val(key: str) -> str:
    return getattr(rec, key, "") or "" if rec else ""

def _tags(key: str) -> str:
    return ", ".join(rec.get_tags(key)) if rec else ""

def _mark(css_class: str, label: str) -> None:
    st.markdown(
        f'<span class="anno-label {css_class}">{label}</span>',
        unsafe_allow_html=True,
    )

saved = False
send = False
feedback_text = ""
form_values: dict = {}

# ── Folio header — barely there ───────────────────────────────────────────────
st.markdown(
    f'<div class="folio-id">'
    f'<span class="folio-id-col">{selected_col.name}</span>'
    f'<span class="folio-id-file">{current_image.filename}</span>'
    f'<span style="margin-left:auto;">'
    f'<span class="badge badge-{status}">{status.replace("_", " ")}</span>'
    f'</span>'
    f'</div>',
    unsafe_allow_html=True,
)

# ── Object — dominant ─────────────────────────────────────────────────────────
try:
    thumb = make_thumbnail_bytes(current_image.filepath)
    st.image(thumb, use_container_width=True)
except Exception as e:
    st.error(f"Could not load image: {e}")

# ── Rule — measured pause ─────────────────────────────────────────────────────
st.markdown('<hr style="margin:3rem 0 2.5rem;">', unsafe_allow_html=True)

# ── Editorial annotation zone ─────────────────────────────────────────────────
gutter_col, anno_col = st.columns([1, 11])

with gutter_col:
    st.markdown(
        f'<div class="folio-cat-num">'
        f'{idx + 1:02d}<br>'
        f'<span style="color:#EBEBEB;">—</span><br>'
        f'{len(images):02d}'
        f'</div>',
        unsafe_allow_html=True,
    )

with anno_col:
    with st.form(key=f"meta_{current_image.id}"):

        _mark("fld-title", "Title")
        form_values["title"] = st.text_input(
            "Title", value=_val("title"), label_visibility="collapsed"
        )

        _mark("fld-desc", "Description")
        form_values["description"] = st.text_area(
            "Description", value=_val("description"),
            height=130, label_visibility="collapsed",
        )

        _mark("fld-subj", "Subjects")
        raw = st.text_input(
            "Subjects", value=_tags("subjects"), label_visibility="collapsed"
        )
        form_values["subjects"] = [s.strip() for s in raw.split(",") if s.strip()]

        with st.expander("visible text · people · places · dates · objects"):
            _mark("", "Visible text")
            form_values["visible_text"] = st.text_area(
                "Visible text", value=_val("visible_text"),
                height=56, label_visibility="collapsed",
            )
            c1, c2 = st.columns(2)
            with c1:
                _mark("", "People")
                raw = st.text_input(
                    "People", value=_tags("people"), label_visibility="collapsed"
                )
                form_values["people"] = [s.strip() for s in raw.split(",") if s.strip()]
            with c2:
                _mark("", "Dates")
                form_values["dates"] = st.text_input(
                    "Dates", value=_val("dates"), label_visibility="collapsed"
                )
            c3, c4 = st.columns([3, 2])
            with c3:
                _mark("", "Places")
                raw = st.text_input(
                    "Places", value=_tags("places"), label_visibility="collapsed"
                )
                form_values["places"] = [s.strip() for s in raw.split(",") if s.strip()]
            with c4:
                _mark("", "Objects")
                raw = st.text_input(
                    "Objects", value=_tags("objects"), label_visibility="collapsed"
                )
                form_values["objects"] = [s.strip() for s in raw.split(",") if s.strip()]

        with st.expander("uncertainty · reviewer notes"):
            n1, n2 = st.columns(2)
            with n1:
                _mark("", "Uncertainty")
                form_values["uncertainty_notes"] = st.text_area(
                    "Uncertainty", value=_val("uncertainty_notes"),
                    height=64, label_visibility="collapsed",
                )
            with n2:
                _mark("", "Reviewer")
                form_values["reviewer_notes"] = st.text_area(
                    "Reviewer", value=_val("reviewer_notes"),
                    height=64, label_visibility="collapsed",
                )

        _, save_col = st.columns([11, 1])
        with save_col:
            saved = st.form_submit_button(
                "save", type="primary", use_container_width=True
            )

# ── Rule + nav ────────────────────────────────────────────────────────────────
st.markdown('<hr style="margin:2.5rem 0 1.5rem;">', unsafe_allow_html=True)

prev_col, ctr_col, ap_col, fl_col, nxt_col = st.columns([1, 5, 2, 2, 1])

with prev_col:
    if st.button("←", use_container_width=True) and idx > 0:
        st.session_state.img_index -= 1
        st.rerun()
with ctr_col:
    jump = st.number_input(
        "pos", min_value=1, max_value=len(images),
        value=idx + 1, step=1, label_visibility="collapsed",
    )
    if jump - 1 != idx:
        st.session_state.img_index = jump - 1
        st.rerun()
with ap_col:
    if st.button("Approve", use_container_width=True):
        snapshot_revision(db, current_image.id, "approved", revised_by="reviewer")
        set_review_status(db, current_image.id, "approved")
        st.rerun()
with fl_col:
    if st.button("Flag", use_container_width=True):
        set_review_status(db, current_image.id, "flagged")
        st.rerun()
with nxt_col:
    if st.button("→", use_container_width=True) and idx < len(images) - 1:
        st.session_state.img_index += 1
        st.rerun()

# ── Revise + history — below the fold ────────────────────────────────────────
with st.expander("revise ↗"):
    rev_col, _ = st.columns([11, 1])
    with rev_col:
        preset = st.selectbox(
            "Preset",
            [
                "—",
                "Make this description more neutral.",
                "Do not infer the event — describe only what is visible.",
                "Use simpler, public-facing language.",
                "Remove any terms that are potentially offensive or outdated.",
                "Expand the description with more visual detail.",
                "Shorten the description to two sentences.",
            ],
            label_visibility="collapsed",
        )
        feedback_text = st.text_area(
            "Instruction",
            value="" if preset == "—" else preset,
            placeholder="Describe what to change.",
            height=56,
            label_visibility="collapsed",
        )
        _, sc = st.columns([11, 1])
        with sc:
            send = st.button(
                "Send", disabled=not feedback_text.strip(), use_container_width=True
            )

history = get_revision_history(db, current_image.id)
if history:
    with st.expander(f"{len(history)} revision{'s' if len(history) != 1 else ''}"):
        for entry in history:
            ts = entry.revised_at.strftime("%Y-%m-%d %H:%M")
            st.markdown(f"**{ts}** · `{entry.revision_type}` · *{entry.revised_by}*")
            if entry.feedback_given:
                st.caption(entry.feedback_given)
            with st.expander("snapshot"):
                st.json(json.loads(entry.metadata_snapshot))

# ── Effects ───────────────────────────────────────────────────────────────────
if saved:
    snapshot_revision(db, current_image.id, "human_edit", revised_by="reviewer")
    upsert_metadata(db, current_image.id, form_values)
    st.rerun()

if send:
    if not rec:
        st.error("No metadata record yet — save a draft first.")
    else:
        with st.spinner("Revising…"):
            try:
                revised = revise_metadata(
                    image_path=current_image.filepath,
                    current_metadata=rec.to_dict(),
                    feedback=feedback_text,
                    session_context=selected_col.session_context(),
                )
                snapshot_revision(db, current_image.id, "model_revision", feedback=feedback_text)
                upsert_metadata(db, current_image.id, revised)
                set_review_status(db, current_image.id, "revised")
                st.rerun()
            except Exception as e:
                st.error(f"Model error: {e}")
