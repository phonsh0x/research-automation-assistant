"""Literature search page — keyword search, journal watch, result display."""

import streamlit as st

from ui.state import ui_key, clear_search_state, set_page_message
from ui.constants import (
    KEYWORD_TEMPLATES,
    SEARCH_SOURCES,
    SEARCH_PAGE_MODES,
    SORT_OPTIONS,
    SORT_LABELS,
    SEARCH_MODE_OPTIONS,
    SEARCH_MODE_LABELS,
    WATCH_DAY_OPTIONS,
)
from ui.components.layout import render_page_header, render_empty_state
from ui.components.paper_table import render_paper_table
from ui.components.messages import render_page_message
from ui.services.search_ui_service import (
    execute_keyword_search,
    restore_last_search,
    execute_journal_watch,
)


# ============================================================================
# Keyword search helpers
# ============================================================================

def _render_keyword_search():
    """渲染关键词检索页面（所有参数从 session_state 读取/写入）。"""

    with st.expander("药物化学关键词模板（点击展开）"):
        col_t1, col_t2, col_t3 = st.columns(3)
        templates = KEYWORD_TEMPLATES
        with col_t1:
            for i, (label, template) in enumerate(list(templates.items())[:3]):
                if st.button(label, key=f"tpl_{i}", use_container_width=True):
                    st.session_state["search_keyword"] = template
        with col_t2:
            for i, (label, template) in enumerate(list(templates.items())[3:6]):
                if st.button(label, key=f"tpl_{i+3}", use_container_width=True):
                    st.session_state["search_keyword"] = template
        with col_t3:
            for i, (label, template) in enumerate(list(templates.items())[6:]):
                if st.button(label, key=f"tpl_{i+6}", use_container_width=True):
                    st.session_state["search_keyword"] = template

    col1, col2 = st.columns([3, 1])
    with col1:
        keywords = st.text_input(
            "检索关键词",
            value=st.session_state.get("search_keyword", ""),
            placeholder="例如: deep learning medical image segmentation",
            key="search_keyword",
        )
    with col2:
        max_results = st.number_input(
            "最大结果数",
            min_value=5, max_value=100,
            value=st.session_state.get("search_max_results", 20),
            step=5, key="search_max_results",
        )

    col3, col4, col5 = st.columns(3)
    with col3:
        year_from = st.number_input(
            "起始年份", min_value=1900, max_value=2030,
            value=st.session_state.get("search_year_from", 2020),
            key="search_year_from",
        )
    with col4:
        year_to = st.number_input(
            "结束年份", min_value=1900, max_value=2030,
            value=st.session_state.get("search_year_to", 2026),
            key="search_year_to",
        )
    with col5:
        sources = st.multiselect(
            "数据源", options=SEARCH_SOURCES,
            default=st.session_state.get("search_sources", ["openalex"]),
            key="search_sources",
        )

    with st.expander("进阶选项"):
        col_a, col_b = st.columns(2)
        with col_a:
            nsc_boost = st.checkbox(
                "顶刊强化 (Nature/Science/Cell/PNAS)",
                value=st.session_state.get("search_nsc_boost", False),
                help="开启后在关键词中追加 AND (Nature OR Science OR Cell OR PNAS) 过滤",
                key="search_nsc_boost",
            )
            oa_only = st.checkbox(
                "仅 OA 文献",
                value=st.session_state.get("search_oa_only", False),
                key="search_oa_only",
            )
        with col_b:
            sort_by = st.selectbox(
                "排序方式", options=SORT_OPTIONS,
                index=SORT_OPTIONS.index(st.session_state.get("search_sort_by", "relevance")),
                format_func=lambda x: SORT_LABELS[x],
                key="search_sort_by",
            )
            search_mode_sel = st.selectbox(
                "检索策略", options=SEARCH_MODE_OPTIONS,
                index=0 if st.session_state.get("search_mode_sel", "backfill") == "backfill" else 1,
                format_func=lambda x: SEARCH_MODE_LABELS[x],
                key="search_mode_sel",
            )

    col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 1])
    with col_btn1:
        if st.button("开始检索 (关键词)", key=ui_key("search", "search_btn"), type="primary", use_container_width=True):
            if not keywords:
                st.warning("请输入检索关键词。")
            else:
                _execute_search(keywords, sources, year_from, year_to, max_results,
                                sort_by, oa_only, nsc_boost, search_mode_sel)
    with col_btn2:
        if st.button("恢复最近检索结果", key=ui_key("search", "restore_btn"), use_container_width=True):
            _restore_last_search()
    with col_btn3:
        if st.button("清空检索结果", key=ui_key("search", "clear_btn"), use_container_width=True):
            clear_search_state()
            set_page_message("info", "检索结果已清空。")
            st.rerun()

    _display_search_results()


def _execute_search(keywords, sources, year_from, year_to, max_results, sort_by, oa_only, nsc_boost, search_mode):
    params = {
        "keywords": keywords, "sources": sources,
        "year_from": year_from, "year_to": year_to,
        "max_results": max_results, "sort_by": sort_by,
        "oa_only": oa_only, "nsc_boost": nsc_boost, "search_mode": search_mode,
    }

    final_keywords = keywords
    if nsc_boost:
        final_keywords = f"({keywords}) AND (Nature OR Science OR Cell OR PNAS)"

    with st.status(f"正在检索: '{final_keywords}' ...", expanded=True) as status:
        st.write(f"关键词: {final_keywords}")
        st.write(f"数据源: {', '.join(sources)}")
        st.write(f"年份: {year_from} - {year_to}")
        st.write(f"排序: {sort_by}")

        result = execute_keyword_search(params)
        if result["success"]:
            data = result["data"]
            st.session_state["search_results"] = data["papers"]
            st.session_state["search_total_count"] = data["total_count"]
            st.session_state["search_errors"] = data["errors"]
            st.session_state["last_search_query"] = data["last_query"]
            status.update(label=result["message"], state="complete")
            if data["errors"]:
                for err in data["errors"]:
                    st.warning(err)
        else:
            status.update(label="检索失败", state="error")
            st.error(f"检索过程中发生错误: {result['error']}")
            st.session_state["search_results"] = None
            st.session_state["search_total_count"] = 0
            st.session_state["search_errors"] = [result["error"]]


def _restore_last_search():
    result = restore_last_search()
    if not result["success"]:
        set_page_message("error", f"恢复检索结果失败: {result['error']}")
        st.rerun()

    data = result["data"]
    run_dict = data.get("run")
    if run_dict:
        st.info(result["message"])
        papers = data.get("papers", [])
        if papers:
            st.session_state["search_results"] = papers
            st.session_state["search_total_count"] = len(papers)
            st.session_state["search_errors"] = []
            st.session_state["last_search_query"] = {
                "keywords": run_dict["query_keywords"],
                "sources": run_dict["sources_used"].split(",") if run_dict.get("sources_used") else [],
                "year_from": None, "year_to": None,
                "max_results": run_dict["total_found"],
            }
            set_page_message("success", f"已恢复最近检索结果: {len(papers)} 篇论文")
        else:
            set_page_message("warning", "数据库中未找到论文记录。")
    else:
        set_page_message("info", result["message"])
    st.rerun()


def _display_search_results():
    results = st.session_state.get("search_results")
    if not results:
        return

    total_count = st.session_state.get("search_total_count", len(results))
    errors = st.session_state.get("search_errors", [])

    st.divider()
    st.markdown("### 检索结果")
    st.success(f"共找到 {total_count} 篇论文，显示 {len(results)} 条")

    if errors:
        for err in errors:
            st.warning(err)

    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    oa_count = len([p for p in results if p.get("oa_status") in ("gold", "green", "hybrid", "bronze")])
    with col_s1: st.metric("总计", len(results))
    with col_s2: st.metric("OA 可获取", oa_count)
    with col_s3:
        valid_years = [p["year"] for p in results if p.get("year")]
        avg_year = sum(valid_years) / max(len(valid_years), 1) if valid_years else 0
        st.metric("平均年份", f"{avg_year:.1f}")
    with col_s4:
        cited = len([p for p in results if p.get("citation_count", 0) > 0])
        st.metric("有引用", cited)

    table_data = []
    for i, paper in enumerate(results, start=1):
        title = paper.get("title", "")
        table_data.append({
            "序号": i,
            "标题": title[:100] + "..." if len(title) > 100 else title,
            "第一作者": paper.get("authors", "").split(",")[0].strip() if paper.get("authors") else "未知",
            "年份": paper.get("year") or "未知",
            "期刊": (paper.get("journal") or "未知")[:30],
            "OA": paper.get("oa_status", "unknown"),
            "引用": paper.get("citation_count", 0),
            "来源": paper.get("source", ""),
        })

    render_paper_table(table_data, column_config={
        "序号": st.column_config.NumberColumn(width="small"),
        "标题": st.column_config.TextColumn(width="large"),
        "OA": st.column_config.TextColumn(width="small"),
        "引用": st.column_config.NumberColumn(width="small"),
    })

    last_query = st.session_state.get("last_search_query")
    if last_query:
        with st.expander("查询详情"):
            st.json(last_query)


# ============================================================================
# Journal watch
# ============================================================================

def _render_journal_watch():
    from src.paper_search.journal_watchlist import JournalWatchlist  # TODO: move to service

    wl = JournalWatchlist()

    with st.expander("监控期刊清单", expanded=True):
        journals = wl.get_journals(active_only=False)
        if journals:
            journal_data = []
            for j in journals:
                journal_data.append({
                    "期刊": j.get("name", ""),
                    "ISSN": j.get("issn") or j.get("eissn") or "",
                    "分类": j.get("category", ""),
                    "优先级": j.get("priority", 5),
                    "状态": "活跃" if j.get("is_active") else "停用",
                    "RSS": "有" if j.get("rss_url") else "无",
                })
            render_paper_table(journal_data)
        else:
            render_empty_state("期刊清单为空", "请先初始化数据库。")

    st.divider()
    col_d1, col_d2 = st.columns([2, 1])
    with col_d1:
        days = st.selectbox("监控最近天数", options=WATCH_DAY_OPTIONS, index=2, key=ui_key("search", "watch_days"))
    with col_d2:
        active_only = st.checkbox("仅活跃期刊", value=True, key=ui_key("search", "watch_active_only"))

    if st.button("开始监控 (期刊)", key=ui_key("search", "watch_btn"), type="primary", use_container_width=True):
        _execute_journal_watch(days, active_only)


def _execute_journal_watch(days, active_only):
    with st.status(f"期刊监控中（最近 {days} 天）...", expanded=True) as status:
        result = execute_journal_watch(days=days, active_only=active_only)
        if result["success"]:
            data = result["data"]
            if data["deduped"] > 0:
                st.write(f"共发现 {data['deduped']} 篇新论文（新增入库 {data['new_count']} 篇）")
                status.update(label=result["message"], state="complete")
                st.success(f"共发现 {data['deduped']} 篇新论文，其中 {data['new_count']} 篇已入库。")
            else:
                status.update(label="监控完成，未发现新论文", state="complete")
                st.info(result["message"])
            if data.get("errors"):
                for err in data["errors"]:
                    st.warning(err)
        else:
            status.update(label="监控失败", state="error")
            st.error(f"监控失败: {result['error']}")


# ============================================================================
# Page entry point
# ============================================================================

def render():
    render_page_header("文献检索", "通过合法开放 API 检索学术论文。")
    render_page_message()

    search_mode = st.radio(
        "检索模式", options=SEARCH_PAGE_MODES, horizontal=True, key="search_mode",
    )

    if search_mode == "按关键词检索":
        _render_keyword_search()
    else:
        _render_journal_watch()
