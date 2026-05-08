"""
streamlit_app.py — entry point.
Run with: streamlit run streamlit_app.py
"""
import streamlit as st
from app.config import PAGE_TITLE, PAGE_ICON
from app.db.schema import create_tables

# Ensure DB exists on startup
create_tables()

st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    /* Sidebar nav tweaks */
    section[data-testid="stSidebar"] { min-width: 220px; }
    /* Status badges */
    .badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.03em;
    }
    .badge-needs_review  { background: #fef3c7; color: #92400e; }
    .badge-in_progress   { background: #dbeafe; color: #1e40af; }
    .badge-revised       { background: #ede9fe; color: #5b21b6; }
    .badge-approved      { background: #d1fae5; color: #065f46; }
    .badge-flagged       { background: #fee2e2; color: #991b1b; }
</style>
""", unsafe_allow_html=True)

st.title("🖼️ Photo Metadata Review")
st.caption("Local-first metadata review for library photo collections.")

st.info(
    "Use the sidebar to navigate:\n"
    "- **Session Setup** — configure collection parameters\n"
    "- **Review** — view images and edit/approve metadata\n"
    "- **Export** — export approved records"
)
