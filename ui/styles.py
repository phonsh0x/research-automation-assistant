"""
Global styles for Streamlit frontend.

Page config must be the very first Streamlit command; apply_global_styles
injects a small set of utility CSS that keeps the UI readable.
"""

import streamlit as st

_CSS = """
<style>
/* --- Global --- */
.stApp {
    font-family: "Microsoft YaHei", "PingFang SC", "Helvetica Neue", sans-serif;
}

/* --- Hide default Streamlit chrome --- */
#MainMenu {
    visibility: hidden;
}

footer {
    visibility: hidden;
}

[data-testid="stToolbar"] {
    display: none;
}

[data-testid="stDecoration"] {
    display: none;
}

[data-testid="stStatusWidget"] {
    display: none;
}

[data-testid="stSidebarNav"] {
    display: none !important;
}

.stDeployButton {
    display: none;
}

/* --- Stats cards (home page) --- */
[data-testid="stMetric"] {
    background-color: #f8f9fa;
    border-radius: 8px;
    padding: 12px;
    border: 1px solid #e9ecef;
}

/* --- Status badge helpers (inline text) --- */
.oa-gold   { color: #b8860b; font-weight: 600; }
.oa-green  { color: #228b22; font-weight: 600; }
.oa-hybrid { color: #4169e1; font-weight: 600; }
.oa-bronze { color: #8b4513; font-weight: 600; }

/* --- Page titles --- */
h1 {
    font-weight: 700 !important;
}

/* --- Table helpers --- */
[data-testid="stDataFrame"] {
    font-size: 0.88rem;
}
</style>
"""


def apply_page_config():
    """Set Streamlit page config.  Must be called before any other st command."""
    st.set_page_config(
        page_title="科研自动化助手",
        page_icon=":books:",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def apply_global_styles():
    """Inject custom CSS."""
    st.markdown(_CSS, unsafe_allow_html=True)
