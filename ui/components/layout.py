"""Layout primitives — page headers, sections, empty states, dividers."""

import streamlit as st


def render_page_header(title: str, subtitle: str | None = None, icon: str | None = None):
    """Unified page title with optional subtitle and icon."""
    if icon:
        st.title(f"{icon} {title}")
    else:
        st.title(title)
    if subtitle:
        st.markdown(subtitle)


def render_section(title: str, description: str | None = None):
    """Section heading with optional description caption."""
    st.markdown(f"### {title}")
    if description:
        st.caption(description)


def render_empty_state(title: str, description: str, icon: str = "ℹ️"):
    """Placeholder for pages or sections that have no data yet."""
    st.info(f"{icon} **{title}** — {description}")


def render_divider():
    """Unified divider."""
    st.divider()
