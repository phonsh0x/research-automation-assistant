"""Metric card components for stats dashboards."""

import streamlit as st


def render_metric_cards(metrics: list[dict], columns: int = 4):
    """Render a row of `st.metric` cards.

    Each dict in *metrics* may contain:
        label  (str)          — metric label
        value  (str | int)    — displayed value
        delta  (str | None)   — optional delta (e.g. "+12")
        help   (str | None)   — tooltip
    """
    cols = st.columns(columns)
    for i, m in enumerate(metrics):
        with cols[i % columns]:
            st.metric(
                label=m.get("label", "-"),
                value=m.get("value", "N/A"),
                delta=m.get("delta"),
                help=m.get("help"),
            )


def render_database_stats(db_stats: dict, ft_stats: dict):
    """Home-page 4-column overview: papers, PDFs, Markdown, OA."""
    metrics = [
        {"label": "本地论文数", "value": db_stats.get("total_papers", 0)},
        {"label": "已下载 PDF", "value": ft_stats.get("with_pdf", 0)},
        {"label": "已转 Markdown", "value": db_stats.get("total_full_texts", 0)},
        {"label": "OA 论文", "value": ft_stats.get("by_source", {}).get("unpaywall", 0)},
    ]
    render_metric_cards(metrics, columns=4)


def render_fulltext_stats(stats: dict):
    """Fulltext-page 5-column download statistics."""
    metrics = [
        {"label": "论文总数", "value": stats.get("total_papers", 0)},
        {"label": "已有 PDF", "value": stats.get("with_pdf", 0)},
        {"label": "待获取", "value": stats.get("without_pdf", 0)},
        {"label": "需人工审查", "value": stats.get("manual_review", 0)},
        {"label": "失败", "value": stats.get("failed", 0)},
    ]
    render_metric_cards(metrics, columns=5)
