"""Paper table rendering — dataframe, detail view, status badges."""

import streamlit as st


def render_paper_table(
    table_data: list[dict],
    column_config: dict | None = None,
    use_container_width: bool = True,
    hide_index: bool = True,
):
    """Render a Streamlit dataframe from a pre-built list of row dicts.

    The caller is responsible for building *table_data* with the desired
    columns.  This function only handles the ``st.dataframe`` call with
    sensible defaults.
    """
    if not table_data:
        st.caption("(无数据)")
        return

    st.dataframe(
        table_data,
        use_container_width=use_container_width,
        hide_index=hide_index,
        column_config=column_config,
    )


def render_paper_detail(paper: dict):
    """Show a single paper's metadata as a key-value list."""
    fields = [
        ("DOI", paper.get("doi")),
        ("期刊", paper.get("journal")),
        ("年份", paper.get("year")),
        ("作者", paper.get("authors")),
        ("OA 状态", paper.get("oa_status")),
        ("来源", paper.get("source")),
        ("PDF 路径", paper.get("pdf_path")),
    ]
    for label, value in fields:
        if value:
            st.markdown(f"**{label}**: {value}")

    abstract = paper.get("abstract")
    if abstract:
        with st.expander("摘要"):
            st.markdown(abstract)


def render_fulltext_status_badge(access_status: str, legal_status: str | None = None):
    """Render coloured badges for fulltext access and legal status."""
    status_colours = {
        "downloaded": "#228b22",
        "pending": "#6c757d",
        "attempted": "#fd7e14",
        "failed": "#dc3545",
        "manual_review": "#0d6efd",
        "manual_upload": "#20c997",
    }
    legal_colours = {
        "合法 OA": "#228b22",
        "合法订阅": "#0d6efd",
        "用户负责": "#fd7e14",
        "需人工确认": "#ffc107",
        "禁止": "#dc3545",
    }

    colour = status_colours.get(access_status, "#6c757d")
    st.markdown(
        f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
        f'background:{colour};color:#fff;font-size:0.82rem;margin-right:6px;">'
        f'{access_status}</span>',
        unsafe_allow_html=True,
    )
    if legal_status:
        lc = legal_colours.get(legal_status, "#6c757d")
        st.markdown(
            f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
            f'background:{lc};color:#fff;font-size:0.82rem;">'
            f'{legal_status}</span>',
            unsafe_allow_html=True,
        )
