"""Filter widget helpers.

Every widget receives an explicit ``key`` via ``ui.state.ui_key`` so
that DuplicateElementId can never occur.
"""

import streamlit as st

from ui.state import ui_key


def render_text_filter(
    label: str,
    key: str,
    placeholder: str = "",
    value: str = "",
) -> str:
    """Thin wrapper around ``st.text_input`` with explicit key."""
    return st.text_input(
        label,
        value=value,
        placeholder=placeholder,
        key=key,
    )


def render_year_range_filter(
    prefix: str,
    year_from_default: int = 2020,
    year_to_default: int = 2026,
) -> tuple[int, int]:
    """Render year-from / year-to number inputs in two columns.

    Returns ``(year_from, year_to)``.
    """
    c1, c2 = st.columns(2)
    with c1:
        year_from = st.number_input(
            "起始年份",
            min_value=1900,
            max_value=2030,
            value=year_from_default,
            key=ui_key(prefix, "year_from"),
        )
    with c2:
        year_to = st.number_input(
            "结束年份",
            min_value=1900,
            max_value=2030,
            value=year_to_default,
            key=ui_key(prefix, "year_to"),
        )
    return year_from, year_to


def render_source_filter(
    prefix: str,
    options: list[str],
    default: list[str] | None = None,
) -> list[str]:
    """Render a multi-select data-source picker."""
    if default is None:
        default = [options[0]] if options else []
    return st.multiselect(
        "数据源",
        options=options,
        default=default,
        key=ui_key(prefix, "sources"),
    )


def render_limit_select(
    prefix: str,
    options: list[int],
    default: int = 20,
) -> int:
    """Render a result-count selectbox."""
    idx = options.index(default) if default in options else 1
    return st.selectbox(
        "显示数量",
        options=options,
        index=idx,
        key=ui_key(prefix, "limit"),
    )
