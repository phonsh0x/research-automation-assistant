"""Fulltext download page — checkbox cards + unified selection toolbar.

Regions:
  1. Page header
  2. Stats overview
  3. Filter bar
  4. Download tips
  5. Pending-papers checkbox cards + toolbar
  6. Batch / single operations
  7. Institution access (gated)
  8. Manual upload (gated)
  9. Recent results
 10. Advanced debug (collapsed)
 11. Legal notice
"""

import streamlit as st

from ui.state import (
    ui_key,
    set_page_message,
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
from ui.components.messages import render_page_message
from ui.components.selection_toolbar import (
    render_selection_toolbar,
    checkbox_key_for,
)
from ui.services.repository_service import get_download_stats, get_pending_papers, clear_cached_stats
from ui.services.fulltext_ui_service import (
    resolve_fulltext,
    download_fulltext,
    batch_download_pending,
    mark_manual_review,
    handle_manual_upload,
)

SCOPE = "fulltext"


# ============================================================================
# Region 2 — Stats overview
# ============================================================================

def _render_stats_section():
    result = get_download_stats()
    stats = result.get("data", {})

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
# Region 4 — Download tips
# ============================================================================

def _render_download_tips():
    with st.expander("下载前提示", expanded=False):
        st.caption("• OpenAlex / Crossref / PubMed 负责**元数据检索**，不保证 PDF 全文。")
        st.caption("• 真正下载 PDF 依赖 **Unpaywall / PMC / arXiv / 出版社 OA / 校园网授权 / 手动上传**。")
        from src.config import get_config
        if not get_config("unpaywall.email", ""):
            st.warning("⚠ Unpaywall email 未配置，建议前往「系统设置 → API 配置」添加。")
        st.caption("• 若 DOI 为测试 DOI（如 10.9999 开头），无法用于真实下载验证。")
        st.caption("• 结果为「未找到合法全文」时，说明所有合法来源均不可用，可尝试校园网授权或手动上传。")


# ============================================================================
# Region 5 — Pending papers cards + toolbar
# ============================================================================

def _render_pending_papers_section():
    """Checkbox cards + unified toolbar.  Returns nothing — operations are inline."""
    render_section("待获取全文的论文")
    _render_download_tips()

    # Limit + refresh
    c_f1, c_f2 = st.columns([2, 1])
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

    # Fetch & filter
    result = get_pending_papers(limit=limit)
    all_papers = result.get("data", {}).get("papers", [])
    papers = _apply_filters(all_papers)

    if not papers:
        if all_papers:
            st.caption("筛选条件过严，没有匹配的论文。")
        else:
            render_empty_state("全文获取完成", "所有论文均已有 PDF，无需获取。", icon="✅")
        return

    all_ids = [p.get("paper_id") for p in papers if p.get("paper_id")]

    # Unified selection toolbar
    batch_clicked, selected_ids = render_selection_toolbar(
        scope=SCOPE,
        item_ids=all_ids,
        batch_label="批量获取所选论文",
    )

    if batch_clicked and selected_ids:
        _execute_batch_download(selected_ids, all_ids)
        st.rerun()

    st.divider()

    # Paper cards with inline actions
    for p in papers:
        pid = p.get("paper_id")
        if not pid:
            continue
        title = p.get("title") or "未命名论文"
        authors = p.get("authors") or "未知"
        if len(authors) > 80:
            authors = authors[:80] + "..."
        year = p.get("year") or "—"
        journal = p.get("journal") or "—"
        doi = p.get("doi") or "—"
        oa = p.get("oa_status") or "—"
        dl_status = p.get("download_status") or "pending"

        cc1, cc2, cc3 = st.columns([0.06, 0.64, 0.30])
        with cc1:
            st.checkbox("", key=checkbox_key_for(SCOPE, pid), label_visibility="collapsed")
        with cc2:
            st.markdown(f"**{title}**")
            st.caption(f"作者：{authors}")
            st.caption(f"年份：{year} ｜ 期刊：{journal} ｜ DOI：{doi}")
            st.caption(f"OA：{oa} ｜ 下载状态：{dl_status}")
        with cc3:
            c_act1, c_act2, c_act3 = st.columns(3)
            with c_act1:
                if st.button("查询来源", key=ui_key("fulltext", "resolve", pid), use_container_width=True):
                    with st.status("正在查询...", expanded=True) as status:
                        r = resolve_fulltext(pid)
                        if r["success"] and r["data"]:
                            st.session_state[KEY_FT_LAST_RESOLVE_RESULT] = r["data"]
                            d = r["data"]
                            if d.get("pdf_url"):
                                st.success(f"可用来源: {d.get('source', '—')}")
                            else:
                                st.warning(f"未找到可用全文: {d.get('error_message', '—')}")
                            status.update(label="查询完成", state="complete")
                        else:
                            st.error(r["error"] or "查询失败")
                            status.update(label="查询失败", state="error")
            with c_act2:
                if st.button("下载 PDF", key=ui_key("fulltext", "download", pid), use_container_width=True):
                    _do_download(pid)
            with c_act3:
                if st.button("标记审查", key=ui_key("fulltext", "mark_review", pid), use_container_width=True):
                    r = mark_manual_review(pid)
                    if r["success"]:
                        st.success(f"已标记为人工审查")
                        set_page_message("info", "已标记为人工审查，稍后可通过手动上传获取。")
                    else:
                        st.error(r["error"] or "更新失败")

        # Detail expander
        with st.expander(f"详情 — {title[:40]}"):
            _render_paper_detail_inline(p)
        st.divider()


def _render_paper_detail_inline(paper: dict):
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**标题**: {paper.get('title') or '—'}")
        st.markdown(f"**DOI**: `{paper.get('doi') or '—'}`")
        st.markdown(f"**期刊**: {paper.get('journal') or '—'}")
        st.markdown(f"**年份**: {paper.get('year') or '—'}")
        st.markdown(f"**来源**: {paper.get('source') or '—'}")
    with c2:
        st.markdown(f"**OA 状态**: {paper.get('oa_status') or '—'}")
        st.markdown(f"**下载状态**: {paper.get('download_status', '—')}")
        st.markdown(f"**法律状态**: {paper.get('legal_status') or '—'}")
        pdf_path = paper.get("pdf_path")
        st.markdown(f"**PDF 路径**: {pdf_path if pdf_path else '—'}")
        authors = paper.get("authors", "")
        st.markdown(f"**作者**: {authors[:100] if authors else '—'}")

    abstract = paper.get("abstract")
    if abstract:
        st.markdown("**摘要**:")
        st.markdown(abstract[:1500])


# ============================================================================
# Batch download
# ============================================================================

def _execute_batch_download(paper_ids: list[int], all_ids_for_clear: list[int]):
    user_confirmed = st.session_state.get(KEY_FT_INSTITUTION_CONFIRMED, False)
    with st.status(f"正在批量获取 {len(paper_ids)} 篇...", expanded=True) as status:
        result = batch_download_pending(paper_ids, user_confirmed_institution=user_confirmed)
        if result["success"]:
            summary = result.get("summary", {})
            data = result["data"]
            c1, c2, c3, c4, c5, c6 = st.columns(6)
            with c1: st.metric("总计", summary.get("total", 0))
            with c2: st.metric("已下载", summary.get("downloaded", 0))
            with c3: st.metric("未找到全文", summary.get("unavailable", 0))
            with c4: st.metric("需人工处理", summary.get("manual_review", 0))
            with c5: st.metric("程序失败", summary.get("failed", 0))
            with c6: st.metric("跳过", summary.get("skipped", 0))
            for i, r in enumerate(data, start=1):
                access = r.get("access_status", "")
                source_label = r.get("source_label", r.get("source", "—"))
                error = r.get("error_message", "")
                pdf = r.get("pdf_path")
                title = r.get("title") or f"第 {i} 篇"
                if pdf:
                    st.write(f"✅《{title}》下载成功 | 来源：{source_label}")
                elif access == "unavailable":
                    st.write(f"⚪《{title}》未找到合法全文 | 建议：校园网授权访问 / 手动上传")
                elif access == "manual_review":
                    st.write(f"🟡《{title}》需要人工处理 | 原因：{error or '—'}")
                elif access in ("failed", "unsupported_source"):
                    st.write(f"❌《{title}》获取失败 | 原因：{error or source_label}")
                else:
                    st.write(f"⏭️《{title}》已跳过 | 原因：{error or access or '—'}")
            status.update(label=f"批量获取完成", state="complete")
            # Clear selection
            for pid in all_ids_for_clear:
                st.session_state[checkbox_key_for(SCOPE, pid)] = False
        else:
            st.error(f"批量获取失败: {result['error']}")
            status.update(label="批量获取失败", state="error")


# ============================================================================
# Single download
# ============================================================================

def _do_download(paper_id: int):
    with st.status("正在获取全文...", expanded=True) as status:
        result = download_fulltext(paper_id, user_confirmed_institution=False)
        if result["success"] and result["data"]:
            st.session_state[KEY_FT_LAST_DOWNLOAD_RESULT] = result["data"]
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


# ============================================================================
# Institution access (unchanged)
# ============================================================================

def _render_institution_section():
    render_divider()
    render_section("校园网授权访问")
    st.markdown("""
    **合规声明**：此功能仅用于用户已通过校园网/学校 VPN/图书馆代理
    获得合法机构授权的资源。系统**不会**保存账号密码、不会自动登录
    统一认证、不会绕过验证码或付费墙。
    """)

    confirmed = st.checkbox(
        "我确认已通过校园网 / 学校 VPN / 图书馆代理获得机构授权，"
        "并仅用于学校授权科研用途。",
        value=st.session_state.get(KEY_FT_INSTITUTION_CONFIRMED, False),
        key=KEY_FT_INSTITUTION_CONFIRMED,
    )
    st.session_state[KEY_INSTITUTION_ACCESS_CONFIRMED] = confirmed

    debug_id = st.number_input(
        "论文 ID", min_value=1, step=1, value=1,
        key=ui_key("fulltext", "institution_paper_id"),
    )
    if st.button("通过校园网授权访问下载", key=ui_key("fulltext", "institution_download"),
                 type="primary", use_container_width=True, disabled=not confirmed):
        if not confirmed:
            st.warning("请先勾选机构授权确认。")
        else:
            with st.status("正在通过机构网络获取...", expanded=True) as status:
                r = download_fulltext(debug_id, user_confirmed_institution=True)
                if r["success"] and r["data"]:
                    d = r["data"]
                    st.session_state[KEY_FT_LAST_DOWNLOAD_RESULT] = d
                    if d.get("pdf_path"):
                        st.success(f"机构下载成功: {d['pdf_path']}")
                        status.update(label="下载完成", state="complete")
                    else:
                        st.warning(f"下载失败: {d.get('error_message')}")
                        status.update(label="下载失败", state="error")
                else:
                    st.error(f"下载失败: {r['error']}")
                    status.update(label="失败", state="error")


# ============================================================================
# Manual upload (unchanged)
# ============================================================================

def _render_manual_upload_section():
    render_divider()
    render_section("人工上传 PDF")
    st.caption("系统将自动从 PDF 提取 DOI 和标题，匹配已有论文或新建记录。无需手动输入 ID。")

    rights_ok = st.checkbox(
        "我确认该 PDF 来自合法途径，并有权在课题组内部科研使用。",
        value=st.session_state.get(KEY_FT_UPLOAD_RIGHTS_CONFIRMED, False),
        key=KEY_FT_UPLOAD_RIGHTS_CONFIRMED,
    )

    upload_files = st.file_uploader(
        "选择 PDF 文件（可多选）", type=["pdf"], accept_multiple_files=True,
        key=ui_key("fulltext", "upload_files"),
    )

    if upload_files:
        if st.button("上传并自动归档", key=ui_key("fulltext", "upload_btn"),
                     type="primary", disabled=not rights_ok):
            if not rights_ok:
                st.warning("请先确认版权合规。")
            else:
                import tempfile, json
                from pathlib import Path
                from src.tasks.manager import get_task_manager

                # Stage files to disk first (Streamlit UploadedFile can't go cross-thread)
                staged_dir = Path(tempfile.gettempdir()) / "paper_uploads"
                staged_dir.mkdir(parents=True, exist_ok=True)
                file_list = []
                for uf in upload_files:
                    dest = staged_dir / uf.name
                    dest.write_bytes(uf.read())
                    file_list.append({"path": str(dest), "name": uf.name})

                mgr = get_task_manager()
                job_id = mgr.submit(
                    "pdf_upload_ingest",
                    f"上传归档 {len(file_list)} 个 PDF",
                    {"files": file_list},
                )
                st.success(f"已创建上传归档任务，请点击「刷新数据」查看进度。")
                st.info(f"共 {len(file_list)} 个文件等待处理。")

    # Show recent background jobs
    from ui.components.job_status import render_job_status
    render_job_status(limit=10)


# ============================================================================
# Recent results (unchanged)
# ============================================================================

def _render_recent_results_section():
    last_resolve = st.session_state.get(KEY_FT_LAST_RESOLVE_RESULT)
    last_download = st.session_state.get(KEY_FT_LAST_DOWNLOAD_RESULT)
    last_upload = st.session_state.get(KEY_FT_LAST_UPLOAD_RESULT)

    if not (last_resolve or last_download or last_upload):
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
# Advanced debug
# ============================================================================

def _render_advanced_debug():
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
                with st.status("查询中...", expanded=True) as s:
                    r = resolve_fulltext(debug_id)
                    if r["success"] and r["data"]:
                        st.session_state[KEY_FT_LAST_RESOLVE_RESULT] = r["data"]
                        st.success(f"来源: {r['data'].get('source', '—')}")
                        s.update(label="完成", state="complete")
                    else:
                        st.error(r["error"] or "失败")
                        s.update(label="失败", state="error")
        with c3:
            if st.button("调试-下载", key=ui_key("fulltext", "debug_download"), use_container_width=True):
                _do_download(debug_id)


# ============================================================================
# Legal notice
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
    _render_pending_papers_section()
    _render_institution_section()
    _render_manual_upload_section()
    _render_recent_results_section()
    _render_advanced_debug()
    _render_legal_notice()
