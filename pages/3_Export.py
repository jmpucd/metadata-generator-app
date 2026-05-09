"""
pages/3_Export.py — export approved metadata.
"""
import streamlit as st
from pathlib import Path

from app.db.schema import create_tables, get_session
from app.db.crud import list_collections, get_approved_records, status_counts
from app.export import export_json, export_csv, export_xmp
from app.config import EXPORTS_DIR

create_tables()

st.header("Export")

db = get_session()
collections = list_collections(db)

if not collections:
    st.warning("No collections found.")
    st.stop()

col_names = ["All collections"] + [c.name for c in collections]
selected = st.selectbox("Collection", col_names)

selected_col = next((c for c in collections if c.name == selected), None)
col_id = selected_col.id if selected_col else None

# Status summary
counts = status_counts(db, collection_id=col_id)
approved_count = counts.get("approved", 0)
total = sum(counts.values())

col1, col2, col3 = st.columns(3)
col1.metric("Total images", total)
col2.metric("Approved", approved_count)
col3.metric("Pending", total - approved_count)

if approved_count == 0:
    st.info("No approved records to export yet. Approve records in the Review tab.")
    st.stop()

st.markdown('<span class="section-label">Export Format</span>', unsafe_allow_html=True)

fmt = st.radio("Format", ["JSON", "CSV", "XMP sidecars"], horizontal=True)

custom_path = st.text_input(
    "Output path (optional — leave blank for default)",
    placeholder=str(EXPORTS_DIR / "approved_metadata.json"),
)

if st.button(f"Export {approved_count} approved records as {fmt}", type="primary"):
    records = get_approved_records(db, collection_id=col_id)
    out_path = Path(custom_path) if custom_path.strip() else None

    with st.spinner("Exporting…"):
        try:
            if fmt == "JSON":
                result = export_json(records, out_path)
                st.success(f"Exported to `{result}`")
            elif fmt == "CSV":
                result = export_csv(records, out_path)
                st.success(f"Exported to `{result}`")
            elif fmt == "XMP sidecars":
                out_dir = Path(custom_path) if custom_path.strip() else None
                written = export_xmp(records, out_dir)
                st.success(f"Wrote {len(written)} XMP sidecar files to `{written[0].parent}`")
        except Exception as e:
            st.error(f"Export failed: {e}")
