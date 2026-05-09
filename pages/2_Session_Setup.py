"""
pages/2_Session_Setup.py — configure a collection / review session.
"""
import streamlit as st
from app.db.schema import create_tables, get_session
from app.db.crud import (
    get_or_create_collection,
    list_collections,
    update_collection,
)

create_tables()

st.header("Session Setup")
st.caption("Define the parameters that guide the local model's metadata generation.")

db = get_session()
collections = list_collections(db)
collection_names = [c.name for c in collections]

# ── Select or create collection ───────────────────────────────────────────────
with st.sidebar:
    st.subheader("Collection")
    mode = st.radio("Action", ["Create new", "Edit existing"], horizontal=True)

if mode == "Create new":
    col_name = st.text_input("Collection name *", placeholder="e.g. Farm Life 1940s")
else:
    if not collection_names:
        st.warning("No collections yet. Create one first.")
        st.stop()
    col_name = st.selectbox("Select collection", collection_names)

# ── Load existing values if editing ──────────────────────────────────────────
existing = next((c for c in collections if c.name == col_name), None)
ev = lambda field, default="": getattr(existing, field, None) or default

with st.form("session_form"):
    st.markdown('<span class="section-label">Collection Details</span>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        description_style = st.text_area(
            "Description style",
            value=ev("description_style"),
            placeholder="e.g. Neutral, third-person, public-facing. Avoid jargon.",
            height=100,
        )
        known_date_range = st.text_input(
            "Known date range",
            value=ev("known_date_range"),
            placeholder="e.g. 1935–1955",
        )
        known_locations = st.text_area(
            "Known locations",
            value=ev("known_locations"),
            placeholder="e.g. Riverside County, California; Smith Family Farm",
            height=80,
        )
    with c2:
        known_people_orgs = st.text_area(
            "Known people / organisations",
            value=ev("known_people_orgs"),
            placeholder="e.g. John Smith (farmer), County Agricultural Extension Office",
            height=100,
        )
        controlled_vocabulary = st.text_area(
            "Controlled vocabulary notes",
            value=ev("controlled_vocabulary"),
            placeholder="e.g. Use 'agricultural equipment' not 'farm machinery'",
            height=80,
        )

    st.markdown('<span class="section-label">Rules &amp; Constraints</span>', unsafe_allow_html=True)
    c3, c4 = st.columns(2)
    with c3:
        terms_to_avoid = st.text_area(
            "Terms to avoid",
            value=ev("terms_to_avoid"),
            placeholder="e.g. 'Negro', 'Orientals', outdated occupational terms",
            height=80,
        )
        institutional_rules = st.text_area(
            "Institutional description rules",
            value=ev("institutional_rules"),
            placeholder="e.g. Do not infer emotion. Do not name living individuals without consent.",
            height=100,
        )
    with c4:
        rights_sensitivity_notes = st.text_area(
            "Rights / sensitivity notes",
            value=ev("rights_sensitivity_notes"),
            placeholder="e.g. Images may contain minors. Some images restricted to staff only.",
            height=100,
        )

    submitted = st.form_submit_button("Save collection settings", type="primary")

if submitted:
    if not col_name:
        st.error("Collection name is required.")
    else:
        kwargs = dict(
            description_style=description_style,
            known_date_range=known_date_range,
            known_locations=known_locations,
            known_people_orgs=known_people_orgs,
            controlled_vocabulary=controlled_vocabulary,
            terms_to_avoid=terms_to_avoid,
            institutional_rules=institutional_rules,
            rights_sensitivity_notes=rights_sensitivity_notes,
        )
        if existing and mode == "Edit existing":
            update_collection(db, existing.id, **kwargs)
            st.success(f"Updated collection: **{col_name}**")
        else:
            get_or_create_collection(db, col_name, **kwargs)
            st.success(f"Created collection: **{col_name}**")

# ── Show existing collections ─────────────────────────────────────────────────
if collections:
    with st.expander("All collections", expanded=False):
        for c in collections:
            st.markdown(f"**{c.name}** — created {c.created_at.strftime('%Y-%m-%d')}")
