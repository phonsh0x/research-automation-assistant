"""Unified selection toolbar for checkbox-based paper lists.

Usage::

    from ui.components.selection_toolbar import (
        render_selection_toolbar, checkbox_key_for, selected_ids_for,
    )

    # At top of page, before rendering paper cards:
    batch_clicked, selected_ids = render_selection_toolbar(
        scope="fulltext",
        item_ids=all_ids,
        batch_label="批量获取所选论文",
    )
    if batch_clicked and selected_ids:
        # execute batch operation

    # For each paper card:
    ck = checkbox_key_for("fulltext", paper_id)
    st.checkbox("选择论文", key=ck, label_visibility="collapsed")

    # Read selected IDs:
    selected = selected_ids_for("fulltext", papers)
"""

import streamlit as st

from ui.state import ui_key

# Session-state key for the shared list (per scope).
_SELECTED_KEY_PREFIX = ".selected_ids"


def _selected_key(scope: str) -> str:
    return f"{scope}{_SELECTED_KEY_PREFIX}"


def checkbox_key_for(scope: str, paper_id: int) -> str:
    """Return the widget key for a single paper's checkbox."""
    return ui_key(f"{scope}_select", paper_id)


def selected_ids_for(scope: str, papers: list[dict]) -> list[int]:
    """Reconstruct selected-id list from individual checkbox widget states."""
    ids = []
    for p in papers:
        pid = p["paper_id"]
        if st.session_state.get(checkbox_key_for(scope, pid), False):
            ids.append(pid)
    return ids


def render_selection_toolbar(
    scope: str,
    item_ids: list[int],
    batch_label: str,
    top_n_options: list[int] | None = None,
) -> tuple[bool, list[int]]:
    """Render the unified selection toolbar.

    Returns ``(batch_clicked, selected_ids)``.

    The toolbar synchronises a shared ``selected_ids`` list with per-item
    checkbox widget keys so that Streamlit 1.39.1 state stays consistent.
    """
    if top_n_options is None:
        top_n_options = [5, 10, 20, 50]

    # Ensure shared list exists
    sk = _selected_key(scope)
    if sk not in st.session_state:
        st.session_state[sk] = []

    all_ids_list = list(item_ids)
    total = len(all_ids_list)

    c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1.5, 1.5])

    with c1:
        if st.button("全选当前页", key=ui_key(scope, "select_all"), use_container_width=True):
            for pid in all_ids_list:
                st.session_state[checkbox_key_for(scope, pid)] = True
            st.session_state[sk] = list(all_ids_list)
            st.rerun()

    with c2:
        if st.button("取消全选", key=ui_key(scope, "deselect_all"), use_container_width=True):
            for pid in all_ids_list:
                st.session_state[checkbox_key_for(scope, pid)] = False
            st.session_state[sk] = []
            st.rerun()

    with c3:
        top_n = st.selectbox(
            "前 N 项", options=top_n_options,
            key=ui_key(scope, "top_n_value"),
            label_visibility="collapsed",
        )
        if st.button(f"选择前 {top_n} 项", key=ui_key(scope, "select_top_n"), use_container_width=True):
            selected = all_ids_list[:min(top_n, total)]
            for pid in all_ids_list:
                st.session_state[checkbox_key_for(scope, pid)] = (pid in selected)
            st.session_state[sk] = selected
            st.rerun()

    # Compute current selection from checkbox states
    selected_ids = []
    for pid in all_ids_list:
        if st.session_state.get(checkbox_key_for(scope, pid), False):
            selected_ids.append(pid)
    st.session_state[sk] = selected_ids
    count = len(selected_ids)

    with c4:
        st.markdown(f"**已选择 {count} / 当前页 {total} 篇**")

    with c5:
        batch_clicked = st.button(
            batch_label, key=ui_key(scope, "batch_selected"),
            type="primary", use_container_width=True,
            disabled=count == 0,
        )

    return batch_clicked, selected_ids
