"""
Session state management for Streamlit frontend.

Centralises all st.session_state key constants, initialisation,
and cross-page state helpers (clear, message pass).
"""

import streamlit as st

# ============================================================================
# Key constants — namespace-style aliases for legacy flat keys.
# New code should reference these constants; the underlying session_state
# keys remain the flat strings for backward compatibility.
# ============================================================================

# --- App ---
KEY_CURRENT_PAGE = "current_page"

# --- Search ---
KEY_SEARCH_KEYWORD = "search_keyword"
KEY_SEARCH_SOURCES = "search_sources"
KEY_SEARCH_YEAR_FROM = "search_year_from"
KEY_SEARCH_YEAR_TO = "search_year_to"
KEY_SEARCH_MAX_RESULTS = "search_max_results"
KEY_SEARCH_SORT_BY = "search_sort_by"
KEY_SEARCH_OA_ONLY = "search_oa_only"
KEY_SEARCH_NSC_BOOST = "search_nsc_boost"
KEY_SEARCH_MODE_SEL = "search_mode_sel"
KEY_SEARCH_RESULTS = "search_results"
KEY_LAST_SEARCH_QUERY = "last_search_query"
KEY_SEARCH_TOTAL_COUNT = "search_total_count"
KEY_SEARCH_ERRORS = "search_errors"
KEY_SEARCH_TEMPLATE_SELECTED = "search_template_selected"
KEY_SEARCH_LAST_STATS = "search_last_stats"

# --- Library ---
KEY_LIBRARY_KEYWORD = "library_keyword"
KEY_LIBRARY_SOURCE = "library_source"
KEY_LIBRARY_YEAR_FROM = "library_year_from"
KEY_LIBRARY_YEAR_TO = "library_year_to"
KEY_LIBRARY_LIMIT = "library_limit"
KEY_LIBRARY_RESULTS = "library_results"
KEY_LIBRARY_TOTAL_COUNT = "library_total_count"
KEY_SELECTED_PAPER_IDS = "selected_paper_ids"

# --- Fulltext ---
KEY_FULLTEXT_TARGET_PAPER_ID = "fulltext_target_paper_id"
KEY_FULLTEXT_FILTER_LIMIT = "fulltext_filter_limit"
KEY_FULLTEXT_RESOLVE_RESULT = "fulltext_resolve_result"
KEY_FULLTEXT_DOWNLOAD_RESULT = "fulltext_download_result"
KEY_INSTITUTION_ACCESS_CONFIRMED = "institution_access_confirmed"
KEY_UPLOAD_PAPER_ID = "upload_paper_id"
KEY_UPLOAD_MESSAGE = "upload_message"

# --- Cross-page ---
KEY_PAGE_MESSAGE = "page_message"


# ============================================================================
# Widget key factory
# ============================================================================

def ui_key(page: str, name: str, item_id: str | int | None = None) -> str:
    """Generate a unique Streamlit widget key to prevent DuplicateElementId."""
    if item_id is None:
        return f"{page}__{name}"
    return f"{page}__{name}__{item_id}"


# ============================================================================
# Session state initialisation
# ============================================================================

_DEFAULTS: dict[str, object] = {
    KEY_CURRENT_PAGE: "首页 — 系统概览",

    # --- 文献检索 ---
    KEY_SEARCH_KEYWORD: "",
    KEY_SEARCH_SOURCES: ["openalex"],
    KEY_SEARCH_YEAR_FROM: 2020,
    KEY_SEARCH_YEAR_TO: 2026,
    KEY_SEARCH_MAX_RESULTS: 20,
    KEY_SEARCH_SORT_BY: "relevance",
    KEY_SEARCH_OA_ONLY: False,
    KEY_SEARCH_NSC_BOOST: False,
    KEY_SEARCH_MODE_SEL: "backfill",
    KEY_SEARCH_RESULTS: None,
    KEY_LAST_SEARCH_QUERY: None,
    KEY_SEARCH_TOTAL_COUNT: 0,
    KEY_SEARCH_ERRORS: [],
    "search_template_selected": None,
    "search_last_stats": None,

    # --- 文献库 ---
    KEY_LIBRARY_KEYWORD: "",
    KEY_LIBRARY_SOURCE: "全部",
    KEY_LIBRARY_YEAR_FROM: None,
    KEY_LIBRARY_YEAR_TO: None,
    KEY_LIBRARY_LIMIT: 20,
    KEY_LIBRARY_RESULTS: None,
    KEY_LIBRARY_TOTAL_COUNT: 0,
    KEY_SELECTED_PAPER_IDS: [],

    # --- 全文获取 ---
    KEY_FULLTEXT_TARGET_PAPER_ID: 1,
    KEY_FULLTEXT_FILTER_LIMIT: 20,
    KEY_FULLTEXT_RESOLVE_RESULT: None,
    KEY_FULLTEXT_DOWNLOAD_RESULT: None,
    KEY_INSTITUTION_ACCESS_CONFIRMED: False,
    KEY_UPLOAD_PAPER_ID: 1,
    KEY_UPLOAD_MESSAGE: "",

    # --- 跨页面消息 ---
    KEY_PAGE_MESSAGE: None,
}


def init_session_state():
    """Initialise every session_state key with its default value.

    Only sets keys that do not already exist — never overwrites live state.
    """
    for key, value in _DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ============================================================================
# State helpers
# ============================================================================

def clear_search_state():
    """Reset all search-related session_state entries."""
    st.session_state[KEY_SEARCH_RESULTS] = None
    st.session_state[KEY_LAST_SEARCH_QUERY] = None
    st.session_state[KEY_SEARCH_TOTAL_COUNT] = 0
    st.session_state[KEY_SEARCH_ERRORS] = []


def clear_fulltext_state():
    """Reset all fulltext-related session_state entries."""
    st.session_state[KEY_FULLTEXT_RESOLVE_RESULT] = None
    st.session_state[KEY_FULLTEXT_DOWNLOAD_RESULT] = None
    st.session_state[KEY_INSTITUTION_ACCESS_CONFIRMED] = False
    st.session_state[KEY_UPLOAD_MESSAGE] = ""


# ============================================================================
# Cross-page message bus
# ============================================================================

def set_page_message(msg_type: str, msg_text: str):
    """Queue a cross-page message (success / warning / error / info)."""
    st.session_state[KEY_PAGE_MESSAGE] = (msg_type, msg_text)


def pop_page_message():
    """Render the queued cross-page message and clear it.

    Call once near the top of every page.  Idempotent when no message
    is queued.
    """
    msg = st.session_state.get(KEY_PAGE_MESSAGE)
    if msg:
        msg_type, msg_text = msg
        if msg_type == "success":
            st.success(msg_text)
        elif msg_type == "warning":
            st.warning(msg_text)
        elif msg_type == "error":
            st.error(msg_text)
        else:
            st.info(msg_text)
        st.session_state[KEY_PAGE_MESSAGE] = None
