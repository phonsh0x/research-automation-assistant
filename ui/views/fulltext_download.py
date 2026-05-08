"""Fulltext download page — filter, select, resolve, download, upload.

Regions:
  1. Page header
  2. Stats overview
  3. Filter bar
  4. Pending-papers list (with selection)
  5. Selected-paper detail
  6. Operations (resolve / download / mark-review / batch)
  7. Institution access (gated behind checkbox)
  8. Manual upload (gated behind rights confirmation)
  9. Recent results
 10. Advanced debug (collapsed)
 11. Legal notice
"""

import streamlit as st

from ui.state import (
    ui_key,
    set_page_message,
    KEY_FT_SELECTED_PAPER_ID,
    KEY_FT_FILTER_KEYWORD,
    KEY_FT_FILTER_YEAR_FROM,
    KEY_FT_FILTER_YEAR_TO,
    KEY_FT_FILTER_SOURCE,
    KEY_FT_FILTER_ACCESS_STATUS,
    KEY_FT_FILTER_LEGAL_STATUS,
    KEY_FT_LIMIT,
    KEY_FT_LAST_RESOLVE_RESULT,
    KEY_FT_LAST_DOWNLOAD_RESULT,
    KEY_FT_LAST_UPLOAD_RESULT,
    KEY_FT_INSTITUTION_CONFIRMED,
    KEY_FT_UPLOAD_RIGHTS_CONFIRMED,
    KEY_FULLTEXT_RESOLVE_RESULT,
    KEY_FULLTEXT_DOWNLOAD_RESULT,
    KEY_INSTITUTION_ACCESS_CONFIRMED,
    KEY_UPLOAD_MESSAGE,
)
from ui.constants import FULLTEXT_DISPLAY_COUNTS
from ui.components.layout import render_page_header, render_section, render_empty_state, render_divider
from ui.components.metric_cards import render_fulltext_stats
from ui.components.paper_table import render_paper_table, render_paper_detail
from ui.components.messages import render_page_message
from ui.services.repository_service import get_download_stats, get_pending_papers, get_paper_detail, clear_cached_stats
from ui.services.fulltext_ui_service import (
    resolve_fulltext,
    download_fulltext,
    batch_download_pending,
    mark_manual_review,
    handle_manual_upload,
)


# ============================================================================
# Region 2 — Stats overview
# ============================================================================

def _render_stats_section():
    """Download statistics cards + source/legal distributions."""
    result = get_download_stats()
    stats = result.get("data", {})

    # Show upload message if queued, then clear
    msg = st.session_state.get(KEY_UPLOAD_MESSAGE, "")
    if msg:
        st.success(msg)
        st.session_state[KEY_UPLOAD_MESSAGE] = ""

    render_fulltext_stats(stats)

    render_divider()

    c_a, c_b = st.columns(2)
    with c_a:
        st.markdown("#### 按来源分布")
        by_source = stats.get("by_source", {})
        if by_source:
            st.dataframe(
                [{"来源": k, "数量": v} for k, v in by_source.items()],
                use_container_width=True, hide_index=True,
            )
        else:
            st.caption("暂无数据")
    with c_b:
        st.markdown("#### 按法律状态分布")
        by_legal = stats.get("by_legal_status", {})
        if by_legal:
            st.dataframe(
                [{"法律状态": k, "数量": v} for k, v in by_legal.items()],
                use_container_width=True, hide_index=True,
            )
        else:
            st.caption("暂无数据")


# ============================================================================
# Region 3 — Filter bar
# ============================================================================

def _render_filter_section():
    """Keyword, year-range, source, and status filters for the pending list."""
    with st.expander("筛选条件", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.text_input(
                "关键词筛选",
                value=st.session_state.get(KEY_FT_FILTER_KEYWORD, ""),
                placeholder="按标题/期刊筛选...",
                key=KEY_FT_FILTER_KEYWORD,
            )
        with c2:
            st.number_input(
                "起始年份", min_value=1900, max_value=2030,
                value=st.session_state.get(KEY_FT_FILTER_YEAR_FROM) or 1900,
                key=KEY_FT_FILTER_YEAR_FROM,
            )
        with c3:
            st.number_input(
                "结束年份", min_value=1900, max_value=2030,
                value=st.session_state.get(KEY_FT_FILTER_YEAR_TO) or 2030,
                key=KEY_FT_FILTER_YEAR_TO,
            )

        c4, c5, c6 = st.columns(3)
        with c4:
            st.selectbox(
                "数据源", options=["全部", "openalex", "crossref", "pubmed", "europe_pmc"],
                key=KEY_FT_FILTER_SOURCE,
            )
        with c5:
            st.selectbox(
                "获取状态",
                options=["全部", "pending", "attempted", "downloaded", "failed", "manual_review"],
                key=KEY_FT_FILTER_ACCESS_STATUS,
            )
        with c6:
            st.selectbox(
                "法律状态",
                options=["全部", "合法 OA", "合法订阅", "用户负责", "需人工确认", "禁止"],
                key=KEY_FT_FILTER_LEGAL_STATUS,
            )

        c_btn1, c_btn2 = st.columns([1, 5])
        with c_btn1:
            if st.button("重置筛选", key=ui_key("fulltext", "reset_filters"), use_container_width=True):
                st.session_state[KEY_FT_FILTER_KEYWORD] = ""
                st.session_state[KEY_FT_FILTER_YEAR_FROM] = None
                st.session_state[KEY_FT_FILTER_YEAR_TO] = None
                st.session_state[KEY_FT_FILTER_SOURCE] = "全部"
                st.session_state[KEY_FT_FILTER_ACCESS_STATUS] = "全部"
                st.session_state[KEY_FT_FILTER_LEGAL_STATUS] = "全部"
                st.rerun()


def _apply_filters(papers: list[dict]) -> list[dict]:
    """Client-side filter on pending papers."""
    if not papers:
        return papers

    keyword = (st.session_state.get(KEY_FT_FILTER_KEYWORD) or "").strip().lower()
    yf = st.session_state.get(KEY_FT_FILTER_YEAR_FROM)
    yt = st.session_state.get(KEY_FT_FILTER_YEAR_TO)
    src = st.session_state.get(KEY_FT_FILTER_SOURCE, "全部")
    access = st.session_state.get(KEY_FT_FILTER_ACCESS_STATUS, "全部")
    legal = st.session_state.get(KEY_FT_FILTER_LEGAL_STATUS, "全部")

    filtered = []
    for p in papers:
        if keyword:
            title = (p.get("title") or "").lower()
            journal = (p.get("journal") or "").lower()
            if keyword not in title and keyword not in journal:
                continue
        if yf and (p.get("year") or 0) < yf:
            continue
        if yt and (p.get("year") or 9999) > yt:
            continue
        if src != "全部" and p.get("source", "") != src:
            continue
        if access != "全部" and p.get("download_status", "") != access:
            continue
        if legal != "全部" and p.get("legal_status", "") != legal:
            continue
        filtered.append(p)

    return filtered


# ============================================================================
# Region 4 — Pending-papers list
# ============================================================================

def _render_pending_papers_section() -> int | None:
    """Show the pending-papers table and a selectbox for picking one.
    Returns the selected paper_id or None."""
    render_section("待获取全文的论文")

    # Pre-download tips
    with st.expander("下载前提示", expanded=False):
        st.caption("• OpenAlex / Crossref / PubMed 负责**元数据检索**，不保证 PDF 全文。")
        st.caption("• 真正下载 PDF 依赖 **Unpaywall / PMC / arXiv / 出版社 OA / 校园网授权 / 手动上传**。")
        from src.config import get_config
        if not get_config("unpaywall.email", ""):
            st.warning("⚠ Unpaywall email 未配置，建议前往「系统设置 → API 配置」添加。")
        st.caption("• 若 DOI 为测试 DOI（如 10.9999 开头），无法用于真实下载验证。")
        st.caption("• 结果为「未找到合法全文」时，说明所有合法来源均不可用，可尝试校园网授权或手动上传。")

    c_f1, c_f2, c_f3 = st.columns([2, 1, 1])
    with c_f1:
        limit = st.selectbox(
            "显示数量", options=FULLTEXT_DISPLAY_COUNTS,
            index=[10, 20, 50, 100].index(st.session_state.get(KEY_FT_LIMIT, 20))
            if st.session_state.get(KEY_FT_LIMIT, 20) in [10, 20, 50, 100] else 1,
            key=KEY_FT_LIMIT,
        )
    with c_f2:
        if st.button("刷新列表", key=ui_key("fulltext", "refresh_btn"), use_container_width=True):
            clear_cached_stats()
            st.rerun()
    with c_f3:
        batch_btn = st.button("批量获取 (前10篇)", key=ui_key("fulltext", "batch_download_btn"),
                              type="primary", use_container_width=True)

    # Fetch & filter
    result = get_pending_papers(limit=limit)
    all_papers = result.get("data", {}).get("papers", [])
    papers = _apply_filters(all_papers)

    if not papers:
        if all_papers:
            st.caption("筛选条件过严，没有匹配的论文。")
        else:
            render_empty_state("全文获取完成", "所有论文均已有 PDF，无需获取。", icon="✅")
        if batch_btn:
            st.warning("没有可批量获取的论文。")
        return None

    # Build table data + selection labels
    table_data = []
    selection_labels = []
    for p in papers:
        pid = p.get("paper_id", "")
        title = p.get("title") or "无标题"
        short = title[:60] + "..." if len(title) > 60 else title
        selection_labels.append(f"#{pid} — {short}")

        table_data.append({
            "ID": pid,
            "标题": title[:80] + "..." if len(title) > 80 else title,
            "年份": p.get("year") or "—",
            "期刊": (p.get("journal") or "—")[:25],
            "DOI": (p.get("doi") or "—")[:35],
            "来源": p.get("source", "—"),
            "OA 状态": p.get("oa_status", "—"),
            "下载状态": p.get("download_status", "pending"),
        })

    render_paper_table(table_data, column_config={
        "ID": st.column_config.NumberColumn(width="small"),
        "标题": st.column_config.TextColumn(width="large"),
        "年份": st.column_config.NumberColumn(width="small"),
        "期刊": st.column_config.TextColumn(width="medium"),
        "OA 状态": st.column_config.TextColumn(width="small"),
        "下载状态": st.column_config.TextColumn(width="small"),
    })

    # Build label-to-id mapping for safe O(1) lookup
    label_to_id: dict[str, object] = dict(zip(selection_labels, (p.get("paper_id") for p in papers)))

    # Selection — guard against stale session_state values that are no
    # longer in the current option list (e.g. after filter change).
    options = ["—"] + selection_labels
    current_val = st.session_state.get(KEY_FT_SELECTED_PAPER_ID)
    default_idx = 0
    if current_val and current_val != "—" and current_val in label_to_id:
        try:
            default_idx = options.index(current_val)
        except ValueError:
            default_idx = 0

    selected_label = st.selectbox(
        "选择一篇论文以查看详情和执行操作",
        options=options,
        index=default_idx,
        key=KEY_FT_SELECTED_PAPER_ID,
    )

    selected_id = None
    if selected_label and selected_label != "—":
        selected_id = label_to_id.get(selected_label)

    # Batch download
    if batch_btn:
        _execute_batch_download(papers[:10])

    return selected_id


def _execute_batch_download(papers: list[dict]):
    pending_ids = [p["paper_id"] for p in papers]
    user_confirmed = st.session_state.get(KEY_FT_INSTITUTION_CONFIRMED, False)
    with st.status("正在批量获取全文...", expanded=True) as status:
        result = batch_download_pending(pending_ids, user_confirmed_institution=user_confirmed)
        if result["success"]:
            summary = result.get("summary", {})
            data = result["data"]

            # Summary cards
            c1, c2, c3, c4, c5, c6 = st.columns(6)
            with c1:
                st.metric("总计", summary.get("total", len(data)))
            with c2:
                st.metric("已下载", summary.get("downloaded", 0))
            with c3:
                st.metric("未找到全文", summary.get("unavailable", 0))
            with c4:
                st.metric("需人工处理", summary.get("manual_review", 0))
            with c5:
                st.metric("程序失败", summary.get("failed", 0))
            with c6:
                st.metric("跳过", summary.get("skipped", 0))

            # Per-paper results with friendly status
            for r in data:
                pid = r.get("paper_id", "?")
                access = r.get("access_status", "")
                source_label = r.get("source_label", r.get("source", "—"))
                error = r.get("error_message", "")
                pdf = r.get("pdf_path")

                if pdf:
                    st.write(f"✅ #{pid} 下载成功 | 来源：{source_label}")
                elif access == "unavailable":
                    hint = "建议：校园网授权访问 / 手动上传 / 标记人工审查"
                    st.write(f"⚪ #{pid} 未找到合法全文 | 已记录 | {hint}")
                elif access == "manual_review":
                    st.write(f"🟡 #{pid} 需要人工处理 | 原因：{error or '—'}")
                elif access in ("failed", "unsupported_source"):
                    st.write(f"❌ #{pid} 获取失败 | 原因：{error or source_label}")
                else:
                    st.write(f"⏭️ #{pid} 已跳过 | 原因：{error or access or '已有 PDF'}")

            status.update(
                label=f"批量获取: total={summary.get('total', 0)} "
                f"downloaded={summary.get('downloaded', 0)} "
                f"unavailable={summary.get('unavailable', 0)}",
                state="complete",
            )
        else:
            st.error(f"批量获取失败: {result['error']}")
            status.update(label="批量获取失败", state="error")


# ============================================================================
# Region 5 — Selected paper detail
# ============================================================================

def _render_paper_detail_section(paper_id: int) -> dict | None:
    """Load and display the full metadata for the selected paper."""
    detail = get_paper_detail(paper_id)
    if not detail["success"] or not detail["data"]:
        st.warning(f"无法加载论文 #{paper_id} 的详情。")
        return None

    paper = detail["data"]
    st.session_state["fulltext.current_paper"] = paper

    render_divider()
    render_section("选中文献详情")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**标题**: {paper.get('title') or '—'}")
        st.markdown(f"**DOI**: `{paper.get('doi') or '—'}`")
        st.markdown(f"**期刊**: {paper.get('journal') or '—'}")
        st.markdown(f"**年份**: {paper.get('year') or '—'}")
        st.markdown(f"**来源**: {paper.get('source') or '—'}")
    with c2:
        st.markdown(f"**OA 状态**: {paper.get('oa_status') or '—'}")
        download_status = paper.get("download_status", "pending")
        st.markdown(f"**下载状态**: {download_status}")
        st.markdown(f"**法律状态**: {paper.get('legal_status') or '—'}")
        pdf_path = paper.get("pdf_path")
        st.markdown(f"**PDF 路径**: {pdf_path if pdf_path else '—'}")
        authors = paper.get("authors", "")
        st.markdown(f"**作者**: {authors[:100] if authors else '—'}")

    abstract = paper.get("abstract")
    if abstract:
        with st.expander("摘要"):
            st.markdown(abstract)

    return paper


# ============================================================================
# Region 6 — Operations
# ============================================================================

def _render_operations_section(paper_id: int):
    """Resolve, download, mark-review buttons for a single paper."""
    render_divider()
    render_section("合法全文获取操作")

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("查询合法全文来源", key=ui_key("fulltext", "resolve_btn"), use_container_width=True):
            _do_resolve(paper_id)
    with c2:
        if st.button("下载合法 PDF", key=ui_key("fulltext", "download_btn"),
                     type="primary", use_container_width=True):
            _do_download(paper_id)
    with c3:
        if st.button("标记人工审查", key=ui_key("fulltext", "mark_review_btn"), use_container_width=True):
            _do_mark_review(paper_id)

    # Refresh paper state
    if st.button("刷新当前论文状态", key=ui_key("fulltext", "refresh_paper"), use_container_width=True):
        clear_cached_stats()
        st.rerun()


def _do_resolve(paper_id: int):
    """Query all legal sources for a paper."""
    with st.status(f"正在查询 #{paper_id} 的全文来源...", expanded=True) as status:
        result = resolve_fulltext(paper_id)
        if result["success"] and result["data"]:
            st.session_state[KEY_FT_LAST_RESOLVE_RESULT] = result["data"]
            st.session_state[KEY_FULLTEXT_RESOLVE_RESULT] = result["data"]  # legacy
            data = result["data"]
            if data.get("pdf_url"):
                source = data.get("source", "未知")
                st.success(f"可用来源: {source} — {data['pdf_url'][:100]}...")
                status.update(label=f"找到可用来源: {source}", state="complete")
            else:
                st.warning(f"未找到可用全文: {data.get('error_message') or '所有来源均不可用'}")
                status.update(label="未找到可用来源", state="error")
        else:
            st.error(f"查询失败: {result['error']}")
            status.update(label="查询失败", state="error")


def _do_download(paper_id: int):
    """Download a single paper's PDF (OA channels only)."""
    with st.status(f"正在获取 #{paper_id} 全文...", expanded=True) as status:
        result = download_fulltext(paper_id, user_confirmed_institution=False)
        if result["success"] and result["data"]:
            st.session_state[KEY_FT_LAST_DOWNLOAD_RESULT] = result["data"]
            st.session_state[KEY_FULLTEXT_DOWNLOAD_RESULT] = result["data"]  # legacy
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


def _do_mark_review(paper_id: int):
    """Mark a paper as needing manual review."""
    result = mark_manual_review(paper_id)
    if result["success"]:
        st.success(f"#{paper_id} 已标记为人工审查")
        set_page_message("info", f"#{paper_id} 已标记为人工审查，稍后可通过手动上传获取。")
    else:
        st.error(result["error"] or "更新失败")


# ============================================================================
# Region 7 — Institution access
# ============================================================================

def _render_institution_section(paper_id: int | None):
    """Gated institution-network download behind an explicit confirmation."""
    render_divider()
    render_section("校园网授权访问")

    st.markdown("""
    **合规声明**：此功能仅用于用户已通过校园网/学校 VPN/图书馆代理
    获得合法机构授权的资源。系统**不会**保存账号密码、不会自动登录
    统一认证、不会绕过验证码或付费墙。遇到 401 / 403 / 429 / 登录页
    时会自动停止。
    """)

    confirmed = st.checkbox(
        "我确认已通过校园网 / 学校 VPN / 图书馆代理获得机构授权，"
        "并仅用于学校授权科研用途。",
        value=st.session_state.get(KEY_FT_INSTITUTION_CONFIRMED, False),
        key=KEY_FT_INSTITUTION_CONFIRMED,
    )
    # Mirror to legacy key for backward compat
    st.session_state[KEY_INSTITUTION_ACCESS_CONFIRMED] = confirmed

    if not paper_id:
        st.caption("请先从上方选择一篇论文。")
        return

    if st.button("通过校园网授权访问下载", key=ui_key("fulltext", "institution_download"),
                 type="primary", use_container_width=True, disabled=not confirmed):
        if not confirmed:
            st.warning("请先勾选机构授权确认。")
        else:
            with st.status(f"正在通过机构网络获取 #{paper_id}...", expanded=True) as status:
                result = download_fulltext(paper_id, user_confirmed_institution=True)
                if result["success"] and result["data"]:
                    data = result["data"]
                    st.session_state[KEY_FT_LAST_DOWNLOAD_RESULT] = data
                    st.session_state[KEY_FULLTEXT_DOWNLOAD_RESULT] = data
                    if data.get("pdf_path"):
                        st.success(f"机构下载成功: {data['pdf_path']}")
                        status.update(label="下载完成", state="complete")
                    else:
                        st.warning(f"下载失败: {data.get('error_message')}")
                        status.update(label="下载失败", state="error")
                else:
                    st.error(f"下载失败: {result['error']}")
                    status.update(label="失败", state="error")


# ============================================================================
# Region 8 — Manual upload
# ============================================================================

def _render_manual_upload_section():
    """User-provided PDF upload with rights confirmation gate."""
    render_divider()
    render_section("人工上传 PDF")
    st.caption("用于用户从机构网络或其他合法途径获得的 PDF 文件。请确认版权合规。")

    rights_ok = st.checkbox(
        "我确认该 PDF 来自合法途径，并有权在课题组内部科研使用。",
        value=st.session_state.get(KEY_FT_UPLOAD_RIGHTS_CONFIRMED, False),
        key=KEY_FT_UPLOAD_RIGHTS_CONFIRMED,
    )

    c1, c2 = st.columns([1, 1])
    with c1:
        upload_paper_id = st.number_input(
            "论文 ID（上传）", min_value=1, step=1,
            value=st.session_state.get("upload_paper_id", 1),
            key="upload_paper_id",
        )
    with c2:
        upload_file = st.file_uploader("选择 PDF 文件", type=["pdf"], key=ui_key("fulltext", "upload_file"))

    if upload_file and upload_paper_id:
        disabled = not rights_ok
        if st.button("上传并关联", key=ui_key("fulltext", "upload_btn"),
                     type="primary", disabled=disabled):
            if not rights_ok:
                st.warning("请先确认版权合规。")
            else:
                result = handle_manual_upload(upload_paper_id, upload_file, user_confirmed_rights=True)
                if result["success"]:
                    data = result["data"]
                    st.session_state[KEY_UPLOAD_MESSAGE] = result["message"]
                    st.session_state[KEY_FT_LAST_UPLOAD_RESULT] = data
                    st.success(result["message"])
                    if data:
                        st.json({
                            "文件名": data.get("filename", "—"),
                            "文件大小": data.get("file_size", 0),
                            "PDF 路径": data.get("pdf_path", "—"),
                        })
                else:
                    st.error(result["error"] or result["message"] or "上传失败")


# ============================================================================
# Region 9 — Recent results
# ============================================================================

def _render_recent_results_section():
    """Show results from the most recent resolve / download / upload."""
    last_resolve = st.session_state.get(KEY_FT_LAST_RESOLVE_RESULT)
    last_download = st.session_state.get(KEY_FT_LAST_DOWNLOAD_RESULT)
    last_upload = st.session_state.get(KEY_FT_LAST_UPLOAD_RESULT)

    has_any = last_resolve or last_download or last_upload
    if not has_any:
        return

    render_divider()
    render_section("最近操作结果")

    c_clr, _ = st.columns([1, 5])
    with c_clr:
        if st.button("清空操作结果", key=ui_key("fulltext", "clear_results"), use_container_width=True):
            st.session_state[KEY_FT_LAST_RESOLVE_RESULT] = None
            st.session_state[KEY_FT_LAST_DOWNLOAD_RESULT] = None
            st.session_state[KEY_FT_LAST_UPLOAD_RESULT] = None
            st.session_state[KEY_FULLTEXT_RESOLVE_RESULT] = None
            st.session_state[KEY_FULLTEXT_DOWNLOAD_RESULT] = None
            st.rerun()

    if last_resolve:
        with st.expander("最近查询结果"):
            st.json(last_resolve)
    if last_download:
        with st.expander("最近下载结果"):
            st.json(last_download)
    if last_upload:
        with st.expander("最近上传结果"):
            st.json(last_upload)


# ============================================================================
# Region 10 — Advanced debug (collapsed)
# ============================================================================

def _render_advanced_debug():
    """Manual paper_id input — only for development debugging."""
    render_divider()
    with st.expander("高级调试（仅开发使用）", expanded=False):
        st.caption("⚠️ 直接输入 paper_id 进行操作，用于开发调试。")
        c1, c2, c3 = st.columns(3)
        with c1:
            debug_id = st.number_input(
                "Paper ID", min_value=1, step=1, value=1,
                key=ui_key("fulltext", "debug_paper_id"),
            )
        with c2:
            if st.button("调试-查询", key=ui_key("fulltext", "debug_resolve"), use_container_width=True):
                _do_resolve(debug_id)
        with c3:
            if st.button("调试-下载", key=ui_key("fulltext", "debug_download"), use_container_width=True):
                _do_download(debug_id)


# ============================================================================
# Region 11 — Legal notice
# ============================================================================

def _render_legal_notice():
    render_divider()
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


# ============================================================================
# Page entry point
# ============================================================================

def render():
    render_page_header("全文获取 / PDF 下载", "通过合法开放 API 获取学术论文 PDF 全文。")
    render_page_message()

    _render_stats_section()

    render_divider()
    _render_filter_section()

    render_divider()
    selected_paper_id = _render_pending_papers_section()

    if selected_paper_id:
        _render_paper_detail_section(selected_paper_id)
        _render_operations_section(selected_paper_id)
    else:
        st.info("请选择一篇待获取论文以查看详情和执行操作。")

    _render_institution_section(selected_paper_id)
    _render_manual_upload_section()
    _render_recent_results_section()
    _render_advanced_debug()
    _render_legal_notice()
