"""Action button helpers.

Every button receives an explicit key so that widgets never collide.
"""

import streamlit as st


def render_primary_button(label: str, key: str, use_container_width: bool = True) -> bool:
    """Primary (blue) button.  Returns ``True`` when clicked."""
    return st.button(label, key=key, type="primary", use_container_width=use_container_width)


def render_secondary_button(label: str, key: str, use_container_width: bool = True) -> bool:
    """Secondary (outline) button.  Returns ``True`` when clicked."""
    return st.button(label, key=key, use_container_width=use_container_width)


def render_reset_button(label: str, key: str, use_container_width: bool = True) -> bool:
    """Reset / clear button (distinct semantic but renders as secondary)."""
    return st.button(label, key=key, use_container_width=use_container_width)
