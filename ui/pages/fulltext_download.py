"""Fulltext download page — pending PDFs, resolve, download, manual upload."""

import streamlit as st

from ui.state import ui_key, set_page_message
from ui.constants import FULLTEXT_DISPLAY_COUNTS
from ui.components.layout import render_page_header, render_empty_state
from ui.components.metric_cards import render_fulltext_stats
from ui.components.paper_table import render_paper_table
from ui.components.messages import render_page_message
from ui.services.repository_service import get_download_stats, get_pending_papers, clear_cached_stats
from ui.services.fulltext_ui_service import (
    resolve_fulltext,
    download_fulltext,
    batch_download_pending,
    mark_manual_review,
    handle_manual_upload,
)


def render():
    render_page_header("全文获取 / PDF 下载", "通过合法开放 API 获取学术论文 PDF 全文。")
    render_page_message()

    # Stats cards
    stats_result = get_download_stats()
    stats = stats_result.get("data", {})
    ft_message = st.session_state.get("upload_message", "")
    if ft_message:
        st.info(ft_message)
        st.session_state["upload_message"] = ""

    render_fulltext_stats(stats)

    st.divider()

    # Source / legal distributions
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### 按来源分布")
        by_source = stats.get("by_source", {})
        if by_source:
            st.dataframe(
                [{"来源": k, "数量": v} for k, v in by_source.items()],
                use_container_width=True, hide_index=True,
            )
        else:
            st.caption("暂无数据")
    with col_b:
        st.markdown("#### 按法律状态分布")
        by_legal = stats.get("by_legal_status", {})
        if by_legal:
            st.dataframe(
                [{"法律状态": k, "数量": v} for k, v in by_legal.items()],
                use_container_width=True, hide_index=True,
            )
        else:
            st.caption("暂无数据")

    # Institution access confirmation
    st.divider()
    with st.expander("机构网络访问设置", expanded=False):
        col_inst1, col_inst2 = st.columns([1, 2])
        with col_inst1:
            institution_confirmed = st.checkbox(
                "确认我已连接机构网络（校园网/VPN），有权访问机构订阅的期刊全文",
                value=st.session_state.get("institution_access_confirmed", False),
                key="institution_access_confirmed",
            )
        with col_inst2:
            st.caption(
                "勾选后，系统将尝试通过机构网络获取订阅期刊 PDF。"
                "系统不会存储任何机构凭证或密码。"
            )

    st.divider()

    # Pending papers list
    st.markdown("### 待获取全文的论文")

    col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
    with col_f1:
        pending_limit = st.selectbox(
            "显示数量", options=FULLTEXT_DISPLAY_COUNTS,
            index=[10, 20, 50, 100].index(st.session_state.get("fulltext_filter_limit", 20))
            if st.session_state.get("fulltext_filter_limit", 20) in [10, 20, 50, 100] else 1,
            key="fulltext_filter_limit",
        )
    with col_f2:
        refresh_btn = st.button("刷新列表", key=ui_key("fulltext", "refresh_btn"), use_container_width=True)
        if refresh_btn:
            clear_cached_stats()
    with col_f3:
        batch_download_btn = st.button("批量获取 (前10篇)", key=ui_key("fulltext", "batch_download_btn"),
                                       type="primary", use_container_width=True)

    pending_result = get_pending_papers(limit=pending_limit)
    pending_papers = pending_result.get("data", {}).get("papers", [])

    if pending_papers:
        pending_data = []
        for p in pending_papers:
            doi = p.get("doi") or ""
            pending_data.append({
                "ID": p.get("paper_id", ""),
                "标题": (p.get("title") or "无标题")[:80],
                "DOI": doi[:40],
                "年份": p.get("year") or "",
                "期刊": (p.get("journal") or "")[:30],
                "OA状态": p.get("oa_status", "unknown"),
                "下载状态": p.get("download_status", "pending"),
            })

        render_paper_table(pending_data, column_config={
            "ID": st.column_config.NumberColumn(width="small"),
            "标题": st.column_config.TextColumn(width="large"),
            "DOI": st.column_config.TextColumn(width="medium"),
            "OA状态": st.column_config.TextColumn(width="small"),
        })

        # Single-paper operations
        st.markdown("#### 单篇操作")
        col_op1, col_op2, col_op3 = st.columns([1, 1, 2])
        with col_op1:
            target_paper_id = st.number_input(
                "论文 ID", min_value=1, step=1,
                value=st.session_state.get("fulltext_target_paper_id", 1),
                key="fulltext_target_paper_id",
            )
        with col_op2:
            resolve_btn = st.button("查询来源", key=ui_key("fulltext", "resolve_btn"), use_container_width=True)
        with col_op3:
            col_dl, col_mr = st.columns(2)
            with col_dl:
                download_btn = st.button("下载全文", key=ui_key("fulltext", "download_btn"),
                                         type="primary", use_container_width=True)
            with col_mr:
                mark_review_btn = st.button("标记人工审查", key=ui_key("fulltext", "mark_review_btn"),
                                            use_container_width=True)

        # Resolve
        if resolve_btn:
            with st.status(f"正在查询论文 {target_paper_id} 的全文来源...", expanded=True) as status:
                result = resolve_fulltext(target_paper_id)
                if result["success"] and result["data"]:
                    st.session_state["fulltext_resolve_result"] = result["data"]
                    if result["data"].get("pdf_url"):
                        st.success(f"找到可用来源: {result['data']['source']} — {result['data']['pdf_url'][:100]}...")
                    else:
                        st.warning(f"未找到可用全文: {result['data'].get('error_message') or '所有来源均不可用'}")
                    status.update(label="查询完成", state="complete")
                else:
                    st.error(f"查询失败: {result['error']}")
                    status.update(label="查询失败", state="error")

        # Download
        if download_btn:
            with st.status(f"正在获取论文 {target_paper_id} 全文...", expanded=True) as status:
                user_confirmed = st.session_state.get("institution_access_confirmed", False)
                result = download_fulltext(target_paper_id, user_confirmed_institution=user_confirmed)
                if result["success"] and result["data"]:
                    st.session_state["fulltext_download_result"] = result["data"]
                    data = result["data"]
                    if data.get("pdf_path"):
                        st.success(f"PDF 下载成功: {data['pdf_path']} ({data.get('file_size', 0)} 字节)")
                        status.update(label="下载完成", state="complete")
                    else:
                        st.warning(f"获取失败: {data.get('error_message')}")
                        status.update(label="获取失败", state="error")
                else:
                    st.error(f"下载失败: {result['error']}")
                    status.update(label="失败", state="error")

        # Mark manual review
        if mark_review_btn:
            result = mark_manual_review(target_paper_id)
            if result["success"]:
                st.success(f"论文 {target_paper_id} 已标记为人工审查")
                set_page_message("info", f"论文 {target_paper_id} 已标记为人工审查，稍后可通过手动上传获取。")
            else:
                st.error(result["error"] or "更新失败")

        # Batch download
        if batch_download_btn:
            with st.status("正在批量获取全文...", expanded=True) as status:
                pending_ids = [p["paper_id"] for p in pending_papers[:10]]
                user_confirmed = st.session_state.get("institution_access_confirmed", False)
                result = batch_download_pending(pending_ids, user_confirmed_institution=user_confirmed)
                if result["success"]:
                    data = result["data"]
                    success_count = len([r for r in data if r.get("pdf_path")])
                    st.write(f"批量获取完成: 成功 {success_count}/{len(data)}")
                    for r in data:
                        if r.get("pdf_path"):
                            st.write(f"- {r['paper_id']}: {r.get('source', '')} — 已下载")
                        else:
                            st.write(f"- {r['paper_id']}: 失败 — {r.get('error_message', '')}")
                    status.update(label=f"批量获取完成: {success_count}/{len(data)} 成功", state="complete")
                else:
                    st.error(f"批量获取失败: {result['error']}")
                    status.update(label="批量获取失败", state="error")
    else:
        render_empty_state("全文获取完成", "所有论文均已有 PDF，无需获取。", icon="✅")

    st.divider()

    # Manual upload
    st.markdown("### 人工上传 PDF")
    st.caption("用于用户从机构网络或其他合法途径获得的 PDF 文件。请确认版权合规。")

    col_u1, col_u2 = st.columns([1, 1])
    with col_u1:
        upload_paper_id = st.number_input(
            "论文 ID（上传）", min_value=1, step=1,
            value=st.session_state.get("upload_paper_id", 1),
            key="upload_paper_id",
        )
    with col_u2:
        upload_file = st.file_uploader("选择 PDF 文件", type=["pdf"], key=ui_key("fulltext", "upload_file"))

    if upload_file and upload_paper_id:
        if st.button("上传并关联", key=ui_key("fulltext", "upload_btn"), type="primary"):
            result = handle_manual_upload(upload_paper_id, upload_file, user_confirmed_rights=True)
            if result["success"]:
                st.session_state["upload_message"] = result["message"]
                st.success(result["message"])
            else:
                st.error(result["error"] or result["message"] or "上传失败")

    st.divider()

    # Legal notice
    with st.expander("法律声明"):
        st.markdown("""
        #### 全文获取法律合规声明

        本系统仅通过以下合法途径获取论文 PDF:

        | 来源 | 类型 | 法律状态 |
        |------|------|---------|
        | Unpaywall API | OA 元数据查询 | 合法 OA |
        | PubMed Central | OA 全文子集 | 合法 OA |
        | arXiv API | 预印本 | 合法 OA |
        | 出版社 OA 接口 | 金色/混合 OA | 合法 OA |
        | 机构网络访问 | 订阅期刊 | 合法订阅（仅限授权用户） |
        | 人工上传 | 用户提供 | 用户负责版权合规 |

        **严禁使用以下来源:**
        - Sci-Hub 及其所有镜像站
        - Library Genesis (LibGen)
        - 任何绕过付费墙的盗版服务

        机构订阅访问仅在检测到机构网络环境时启用，不存储任何机构凭证。
        """)
