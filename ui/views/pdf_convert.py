"""PDF-to-Markdown conversion page — Phase 2.3.

Unified selection toolbar + checkbox paper cards.
"""

import streamlit as st

from ui.state import ui_key
from ui.components.layout import render_page_header, render_section, render_empty_state
from ui.components.metric_cards import render_metric_cards
from ui.components.messages import render_page_message
from ui.components.selection_toolbar import (
    render_selection_toolbar,
    checkbox_key_for,
)
from ui.services.pdf_convert_ui_service import (
    get_conversion_stats,
    get_pending_papers,
    get_converted_papers,
    convert_single,
    convert_selected,
    get_markdown_preview,
)

SCOPE = "pdf_convert"


def _safe_markdown_filename(title: str | None) -> str:
    """Build a safe Markdown filename for downloads."""
    safe_title = "".join(c for c in (title or "") if c.isalnum() or c in " _-")[:60].strip()
    return f"{safe_title or 'converted_paper'}.md"


def _render_converted_markdown_section(limit: int = 20) -> None:
    """Render recently converted Markdown files with preview/download actions."""
    render_section("\u5df2\u8f6c\u6362 Markdown")

    converted_result = get_converted_papers(limit=limit)
    converted_papers = converted_result.get("data", {}).get("papers", [])

    if not converted_papers:
        render_empty_state(
            "\u6682\u65e0\u5df2\u8f6c\u6362 Markdown",
            "\u5b8c\u6210 PDF \u8f6c\u6362\u540e\uff0c\u8fd9\u91cc\u4f1a\u663e\u793a\u53ef\u9884\u89c8\u548c\u4e0b\u8f7d\u7684 Markdown \u6587\u4ef6\u3002",
        )
        st.divider()
        return

    for p in converted_papers:
        pid = p["paper_id"]
        title = p.get("title") or "\u672a\u547d\u540d\u8bba\u6587"
        authors = p.get("authors") or "\u672a\u77e5"
        if len(authors) > 80:
            authors = authors[:80] + "..."
        year = p.get("year") or "-"
        journal = p.get("journal") or "-"
        doi = p.get("doi") or "-"
        md_label = p.get("md_status_label", "\u5df2\u8f6c\u6362")
        md_path = p.get("md_path") or ""

        cc1, cc2 = st.columns([0.78, 0.22])
        with cc1:
            st.markdown(f"**{title}**")
            st.caption(f"\u4f5c\u8005\uff1a{authors}")
            st.caption(f"\u5e74\u4efd\uff1a{year} \u00b7 \u671f\u520a\uff1a{journal} \u00b7 DOI\uff1a{doi}")
            st.caption(f"Markdown\uff1a{md_label} \u00b7 {md_path}")

        with cc2:
            if st.button("\u9884\u89c8 / \u4e0b\u8f7d", key=ui_key("pdf_converted_preview", pid), use_container_width=True):
                preview_result = get_markdown_preview(pid)
                if preview_result["success"] and preview_result["data"]:
                    md_text = preview_result["data"]
                    with st.expander(f"Markdown \u9884\u89c8 - {title[:40]}", expanded=True):
                        st.markdown(md_text[:8000])
                        if len(md_text) > 8000:
                            st.caption(f"... \u8fd8\u6709 {len(md_text) - 8000} \u5b57\u7b26\u672a\u663e\u793a\u3002")
                    st.download_button(
                        "\u4e0b\u8f7d Markdown",
                        data=md_text,
                        file_name=_safe_markdown_filename(title),
                        mime="text/markdown",
                        key=ui_key("pdf_converted_dl", pid),
                    )
                else:
                    st.warning(preview_result["error"] or "\u65e0\u6cd5\u52a0\u8f7d Markdown \u9884\u89c8")

        st.divider()


def render():
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

    c_refresh, _ = st.columns([1, 5])
    with c_refresh:
        if st.button("刷新数据", key=ui_key("pdf_convert", "refresh"), use_container_width=True):
            st.rerun()

    st.divider()

    _render_converted_markdown_section(limit=20)

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

    # Unified selection toolbar
    batch_clicked, selected_ids = render_selection_toolbar(
        scope=SCOPE,
        item_ids=all_ids,
        batch_label="批量转换所选论文",
    )

    if batch_clicked and selected_ids:
        with st.status(f"正在批量转换 {len(selected_ids)} 篇论文...", expanded=True) as status:
            result = convert_selected(selected_ids)
            if result["success"]:
                d = result["data"]
                c1, c2, c3 = st.columns(3)
                with c1: st.metric("成功", d.get("success_count", 0))
                with c2: st.metric("失败", d.get("failed_count", 0))
                with c3: st.metric("跳过", d.get("skipped_count", 0))
                status.update(label=result["message"], state="complete")
                for pid in all_ids:
                    st.session_state[checkbox_key_for(SCOPE, pid)] = False
                st.rerun()
            else:
                st.error(result["error"] or "批量转换失败")
                status.update(label="批量转换失败", state="error")

    st.divider()

    # Paper card list
    for p in pending_papers:
        pid = p["paper_id"]
        title = p.get("title") or "未命名论文"
        safe_title = "".join(c for c in title if c.isalnum() or c in " _-")[:60].strip() or "converted_paper"
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
            st.checkbox("选择论文", key=checkbox_key_for(SCOPE, pid), label_visibility="collapsed")
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
                                file_name=f"{safe_title}.md", mime="text/markdown",
                                key=ui_key("pdf_convert_dl", pid),
                            )
                        else:
                            st.warning(preview_result["error"] or "无法加载预览")
        st.divider()
