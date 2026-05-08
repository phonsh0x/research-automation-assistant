"""PDF-to-Markdown conversion page — Phase 2.3.

Checkbox-based paper selection with single/batch convert and preview.
"""

import streamlit as st

from ui.state import ui_key
from ui.components.layout import render_page_header, render_section, render_empty_state
from ui.components.metric_cards import render_metric_cards
from ui.components.messages import render_page_message
from ui.services.pdf_convert_ui_service import (
    get_conversion_stats,
    get_pending_papers,
    convert_single,
    convert_selected,
    get_markdown_preview,
)

_SELECTED_KEY = "pdf_convert_selected_ids"


def _checkbox_key(paper_id: int) -> str:
    return ui_key("pdf_convert_select", paper_id)


def _selected_ids_from_checkboxes(papers: list[dict]) -> list[int]:
    """Reconstruct selected-id list from individual checkbox widget states."""
    ids = []
    for p in papers:
        pid = p["paper_id"]
        if st.session_state.get(_checkbox_key(pid), False):
            ids.append(pid)
    return ids


def render():
    # Ensure selected_ids list exists
    if _SELECTED_KEY not in st.session_state:
        st.session_state[_SELECTED_KEY] = []

    render_page_header("PDF 转 Markdown", "将学术 PDF 论文转换为结构化 Markdown。")
    render_page_message()

    # Stats
    stats_result = get_conversion_stats()
    stats = stats_result.get("data", {})
    metrics = [
        {"label": "已下载 PDF", "value": stats.get("with_pdf", 0)},
        {"label": "已转 Markdown", "value": stats.get("with_markdown", 0)},
        {"label": "待转换", "value": stats.get("pending", 0)},
        {"label": "全文记录", "value": stats.get("full_text_records", 0)},
    ]
    render_metric_cards(metrics, columns=4)

    st.divider()

    # Pending papers
    render_section("待转换论文")
    pending_result = get_pending_papers(limit=50)
    pending_papers = pending_result.get("data", {}).get("papers", [])

    if not pending_papers:
        with_pdf = stats.get("with_pdf", 0)
        if with_pdf == 0:
            render_empty_state("暂无 PDF", "请先前往「全文获取 / PDF 下载」页面获取合法 PDF。")
        else:
            render_empty_state("转换完成", "当前没有待转换的 PDF 文件。", icon="✅")
        return

    all_ids = [p["paper_id"] for p in pending_papers]

    # ----- Top action bar (rendered BEFORE checkboxes) -----
    c_bar1, c_bar2, c_bar3, c_bar4 = st.columns([1, 1, 2, 2])
    with c_bar1:
        if st.button("全选", key=ui_key("pdf_convert", "select_all"), use_container_width=True):
            for pid in all_ids:
                st.session_state[_checkbox_key(pid)] = True
            st.session_state[_SELECTED_KEY] = list(all_ids)
            st.rerun()
    with c_bar2:
        if st.button("取消全选", key=ui_key("pdf_convert", "deselect_all"), use_container_width=True):
            for pid in all_ids:
                st.session_state[_checkbox_key(pid)] = False
            st.session_state[_SELECTED_KEY] = []
            st.rerun()

    # Compute current selected IDs from checkbox states
    selected_ids = _selected_ids_from_checkboxes(pending_papers)
    st.session_state[_SELECTED_KEY] = selected_ids
    selected_count = len(selected_ids)

    with c_bar3:
        st.markdown(f"**已选择 {selected_count} 篇论文**")
    with c_bar4:
        if st.button("批量转换所选论文", key=ui_key("pdf_convert", "batch_selected"),
                     type="primary", use_container_width=True, disabled=selected_count == 0):
            if selected_count == 0:
                st.warning("请先选择至少一篇论文。")
            else:
                with st.status(f"正在批量转换 {len(selected_ids)} 篇论文...", expanded=True) as status:
                    result = convert_selected(selected_ids)
                    if result["success"]:
                        d = result["data"]
                        c1, c2, c3 = st.columns(3)
                        with c1: st.metric("成功", d.get("success_count", 0))
                        with c2: st.metric("失败", d.get("failed_count", 0))
                        with c3: st.metric("跳过", d.get("skipped_count", 0))
                        status.update(label=result["message"], state="complete")
                        # Clear selection and individual checkbox states
                        for pid in all_ids:
                            st.session_state[_checkbox_key(pid)] = False
                        st.session_state[_SELECTED_KEY] = []
                        st.rerun()
                    else:
                        st.error(result["error"] or "批量转换失败")
                        status.update(label="批量转换失败", state="error")

    st.divider()

    # ----- Paper card list -----
    for p in pending_papers:
        pid = p["paper_id"]
        title = p.get("title") or "未命名论文"
        authors = p.get("authors") or "未知"
        if len(authors) > 80:
            authors = authors[:80] + "..."
        year = p.get("year") or "—"
        journal = p.get("journal") or "—"
        doi = p.get("doi") or "—"
        pdf_available = p.get("pdf_available", False)
        pdf_label = p.get("pdf_status_label", "未知")
        md_label = p.get("md_status_label", "未转换")

        cc1, cc2, cc3 = st.columns([0.06, 0.74, 0.20])
        with cc1:
            st.checkbox(
                "", key=_checkbox_key(pid),
                label_visibility="collapsed",
            )
        with cc2:
            st.markdown(f"**{title}**")
            st.caption(f"作者：{authors}")
            st.caption(f"年份：{year} ｜ 期刊：{journal} ｜ DOI：{doi}")
            st.caption(f"PDF：{pdf_label} ｜ Markdown：{md_label}")
        with cc3:
            c_act1, c_act2 = st.columns(2)
            with c_act1:
                if st.button("转换", key=ui_key("pdf_convert_single", pid), use_container_width=True):
                    if not pdf_available:
                        st.warning("当前论文没有可用的 PDF 文件，请先在全文获取页面下载或手动上传 PDF。")
                    else:
                        with st.status("正在转换...", expanded=True) as status:
                            result = convert_single(pid)
                            if result["success"]:
                                data = result["data"]
                                st.success(f"已转换《{title}》— 质量分: {data.get('quality_score', 0)}")
                                status.update(label="转换完成", state="complete")
                                st.rerun()
                            else:
                                st.error(result["error"] or "转换失败")
                                status.update(label="转换失败", state="error")
            with c_act2:
                if st.button("预览", key=ui_key("pdf_convert_preview", pid), use_container_width=True):
                    md_available = p.get("md_available", False)
                    if not md_available:
                        st.warning("该论文尚未生成 Markdown，请先转换。")
                    else:
                        preview_result = get_markdown_preview(pid)
                        if preview_result["success"] and preview_result["data"]:
                            md_text = preview_result["data"]
                            with st.expander(f"Markdown 预览 — {title[:40]}", expanded=True):
                                st.markdown(md_text[:8000])
                                if len(md_text) > 8000:
                                    st.caption(f"... 还有 {len(md_text) - 8000} 字符未显示。")
                            st.download_button(
                                "下载 Markdown", data=md_text,
                                file_name=f"paper_{pid}.md", mime="text/markdown",
                                key=ui_key("pdf_convert_dl", pid),
                            )
                        else:
                            st.warning(preview_result["error"] or "无法加载预览")
        st.divider()
