"""Message display helpers — thin wrappers for consistency."""

import streamlit as st

from ui.state import pop_page_message as _pop_page_message


def render_page_message():
    """Render and clear the cross-page message queued in session_state."""
    _pop_page_message()


def render_error_box(message: str):
    """Render an error callout."""
    st.error(message)


def render_success_box(message: str):
    """Render a success callout."""
    st.success(message)


def render_warning_box(message: str):
    """Render a warning callout."""
    st.warning(message)


def render_info_box(message: str):
    """Render an info callout."""
    st.info(message)
