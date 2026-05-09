"""
streamlit_app.py — entry point.
Run with: streamlit run streamlit_app.py
"""
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

import streamlit as st
from app.config import PAGE_TITLE, PAGE_ICON
from app.db.schema import create_tables

create_tables()

st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
/* ── Base ── */
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-weight: 400;
    color: #111;
    background: #fff;
    -webkit-font-smoothing: antialiased;
}
.stApp { background: #fff; }

/* ── Kill Streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }
[data-testid="stSidebarHeader"] { display: none; }

/* ── Breathing room ── */
.block-container {
    padding-top: 2rem !important;
    padding-left: 3rem !important;
    padding-right: 3rem !important;
    max-width: none !important;
}

/* ── Sidebar: white, hairline border ── */
section[data-testid="stSidebar"] {
    background: #fff;
    border-right: 1px solid #EBEBEB;
    min-width: 200px;
}
section[data-testid="stSidebar"] a { color: #111 !important; }
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] {
    border-radius: 0;
    font-size: 0.62rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    font-weight: 400;
    color: #AAAAAA;
    padding: 0.25rem 0.6rem;
    transition: color 0.1s;
}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"]:hover {
    background: transparent;
    color: #111 !important;
}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-selected="true"] {
    background: transparent;
    color: #111 !important;
    font-weight: 600;
}

/* ── Headings ── */
h1, h2, h3,
.stHeadingContainer h1,
.stHeadingContainer h2,
.stHeadingContainer h3 {
    font-weight: 400;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #BBBBBB !important;
}
h1 { font-size: 0.6rem !important; letter-spacing: 0.18em !important; }
h2 { font-size: 0.58rem !important; }
h3 { font-size: 0.56rem !important; }

/* ── Image: object dominates ── */
[data-testid="stImage"] {
    margin: 0.5rem 0 0 !important;
}
[data-testid="stImage"] img {
    max-height: 80vh;
    object-fit: contain;
    display: block;
}

/* ── Inputs — annotation style, no box ── */
input[type="text"],
input[type="number"],
textarea,
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    background: transparent !important;
    border: none !important;
    border-bottom: 1px solid #EBEBEB !important;
    border-radius: 0 !important;
    color: #111 !important;
    font-size: 0.875rem !important;
    line-height: 1.55 !important;
    padding: 4px 0 5px !important;
    box-shadow: none !important;
    transition: border-color 0.15s !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-bottom-color: #999 !important;
    box-shadow: none !important;
    outline: none !important;
}
/* Kill Streamlit's focus glow */
.stTextInput > div, .stTextArea > div,
.stTextInput > div:focus-within, .stTextArea > div:focus-within,
[data-baseweb="input"]:focus-within, [data-baseweb="textarea"]:focus-within,
[data-baseweb="base-input"] { box-shadow: none !important; }

/* ── Number input ── */
input[type="number"] {
    -moz-appearance: textfield;
    text-align: center;
    font-size: 0.7rem !important;
    color: #BBBBBB !important;
    border-bottom-color: transparent !important;
}
input[type="number"]::-webkit-inner-spin-button,
input[type="number"]::-webkit-outer-spin-button { -webkit-appearance: none; }
.stNumberInput button { display: none !important; }

/* ── Selectbox ── */
.stSelectbox > div > div {
    background: transparent !important;
    border: none !important;
    border-bottom: 1px solid #EBEBEB !important;
    border-radius: 0 !important;
    font-size: 0.78rem !important;
    cursor: pointer;
    box-shadow: none !important;
}
.stSelectbox [data-baseweb="select"] svg { opacity: 0.2 !important; }

/* ── Buttons — dematerialised text ── */
.stButton > button {
    background: transparent !important;
    border: none !important;
    color: #CCCCCC;
    font-size: 0.6rem;
    font-weight: 400;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    padding: 0.15rem 0.3rem;
    border-radius: 0;
    transition: color 0.12s;
    box-shadow: none !important;
}
.stButton > button:hover {
    background: transparent !important;
    color: #111 !important;
    box-shadow: none !important;
}
.stButton > button[kind="primary"] {
    color: #555 !important;
    font-weight: 500;
}
.stButton > button[kind="primary"]:hover { color: #111 !important; }
.stButton > button:disabled { color: #E0E0E0 !important; }

/* ── Form submit — ghosted text link ── */
.stFormSubmitButton > button {
    background: transparent !important;
    border: none !important;
    border-bottom: 1px solid #CCCCCC !important;
    color: #BBBBBB !important;
    font-size: 0.55rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.14em !important;
    text-transform: uppercase !important;
    border-radius: 0 !important;
    padding: 0.15rem 0 0.1rem !important;
    box-shadow: none !important;
    transition: color 0.15s, border-color 0.15s !important;
}
.stFormSubmitButton > button:hover {
    color: #111 !important;
    border-bottom-color: #111 !important;
    background: transparent !important;
}

/* ── Form chrome ── */
[data-testid="stForm"] { border: none !important; padding: 0 !important; background: transparent !important; }

/* ── Anno labels (custom HTML, replaces Streamlit labels) ── */
.anno-label {
    display: block;
    font-size: 0.54rem;
    font-weight: 500;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #CCCCCC;
    margin-top: 1.4rem;
    line-height: 1;
}

/* ── Ref ID ── */
.ref-id {
    font-family: "Courier New", "Menlo", monospace;
    font-size: 0.7rem;
    letter-spacing: 0.06em;
    color: #BBBBBB;
    display: block;
}

/* ── Status badges ── */
.badge {
    font-size: 0.52rem;
    font-weight: 400;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    padding: 2px 5px;
    border: 1px solid currentColor;
    display: inline-block;
}
.badge-needs_review { color: #D0D0D0; }
.badge-in_progress  { color: #AAAAAA; }
.badge-revised      { color: #777; }
.badge-approved     { background: #111; color: #fff; border-color: #111; }
.badge-flagged      { color: #111; border-color: #111; }

/* ── Captions ── */
.stCaption, small {
    font-size: 0.6rem;
    color: #CCCCCC;
    letter-spacing: 0.02em;
}
code {
    font-family: "Courier New", monospace;
    font-size: 0.78em;
    color: #CCCCCC;
    background: transparent;
}

/* ── Alerts ── */
.stAlert {
    border-radius: 0 !important;
    font-size: 0.78rem !important;
    border-left-width: 1px !important;
    background: #FAFAFA !important;
}

/* ── Expander ── */
[data-testid="stExpander"] { border: none !important; box-shadow: none !important; }
.streamlit-expanderHeader {
    font-size: 0.58rem;
    font-weight: 400;
    letter-spacing: 0.1em;
    color: #CCCCCC;
    text-transform: uppercase;
    cursor: pointer;
    background: transparent !important;
}

/* ── Divider ── */
hr { border: none; border-top: 1px solid #F4F4F4; margin: 3rem 0; }

/* ── Metrics (Export page) ── */
[data-testid="stMetric"] { background: transparent; border-top: 1px solid #F2F2F2; padding: 0.75rem 0; }
[data-testid="stMetricLabel"] {
    font-size: 0.54rem !important; font-weight: 500; letter-spacing: 0.12em;
    text-transform: uppercase; color: #CCCCCC !important;
}
[data-testid="stMetricValue"] {
    font-size: 2.2rem !important; font-weight: 300;
    color: #111 !important; letter-spacing: -0.03em !important;
}

/* ── Vertical rhythm ── */
[data-testid="stVerticalBlock"] { gap: 0.25rem !important; }

/* ── Number input as plain position counter ── */
.stNumberInput [data-baseweb="input"] {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}
.stNumberInput [data-baseweb="input"]:focus-within { box-shadow: none !important; }

/* ── Expander: minimal, no chrome ── */
[data-testid="stExpander"] summary {
    font-size: 0.55rem !important;
    letter-spacing: 0.1em;
    color: #D0D0D0 !important;
    text-transform: lowercase;
    padding: 0.5rem 0 !important;
    background: transparent !important;
    list-style: none !important;
}
[data-testid="stExpander"] summary::-webkit-details-marker { display: none !important; }
[data-testid="stExpander"] summary svg { display: none !important; }
[data-testid="stExpander"] summary:hover { color: #555 !important; }
[data-testid="stExpander"] > div[data-testid="stExpanderDetails"] {
    padding: 0.25rem 0 0 0 !important;
    border: none !important;
}

/* ── Cursor ── */
.stSelectbox > div, .stRadio > div label,
.stCheckbox > label, .stExpander summary { cursor: pointer; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<p style="font-family:-apple-system,BlinkMacSystemFont,'Helvetica Neue',Helvetica,Arial,sans-serif;
font-size:0.6rem;font-weight:500;letter-spacing:0.16em;text-transform:uppercase;
color:#BBBBBB;margin:0 0 0.1rem;">UC Davis Library</p>
<p style="font-family:-apple-system,BlinkMacSystemFont,'Helvetica Neue',Helvetica,Arial,sans-serif;
font-size:0.6rem;letter-spacing:0.1em;text-transform:uppercase;color:#DDDDDD;margin:0 0 2rem;">
Digital Collections · Metadata Review</p>
""", unsafe_allow_html=True)
