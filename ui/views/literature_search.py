"""Literature search page — keyword search, journal watch, result display.

Regions:
  1. Page header
  2. Quick keyword template chips
  3. Search form (st.form — no per-widget reruns)
  4. Advanced settings expander
  5. Result statistics
  6. Result table + paper selection
  7. Selected paper detail
  8. Action bar (restore / clear)
"""

import streamlit as st

from ui.state import ui_key, clear_search_state, set_page_message
from ui.constants import (
    KEYWORD_TEMPLATES,
    MEDCHEM_CHIPS,
    SEARCH_SOURCES,
    SEARCH_PAGE_MODES,
    SORT_OPTIONS,
    SORT_LABELS,
    SEARCH_MODE_OPTIONS,
    SEARCH_MODE_LABELS,
    WATCH_DAY_OPTIONS,
)
from ui.components.layout import render_page_header, render_section, render_empty_state, render_divider
from ui.components.paper_table import render_paper_table
from ui.components.messages import render_page_message
from ui.services.search_ui_service import (
    execute_keyword_search,
    restore_last_search,
    execute_journal_watch,
)


# ============================================================================
# Region 2 — Quick keyword template chips
# ============================================================================

def _render_template_chips():
    """Compact grid of MedChem keyword chips.  Clicking a chip fills the
    keyword field but does NOT submit the search."""
    with st.expander("药物化学快速关键词", expanded=False):
        st.caption("点击关键词模板自动填入检索框，可手动修改后再检索。")
        templates = list(MEDCHEM_CHIPS.items())
        cols_per_row = 4
        for row_start in range(0, len(templates), cols_per_row):
            row_items = templates[row_start:row_start + cols_per_row]
            cols = st.columns(cols_per_row)
            for idx, (label, query) in enumerate(row_items):
                with cols[idx]:
                    if st.button(
                        label,
                        key=ui_key("search", "chip", row_start + idx),
                        use_container_width=True,
                    ):
                        st.session_state["search_keyword"] = query
                        st.session_state["search_template_selected"] = label


# ============================================================================
# Region 3 — Search form
# ============================================================================

def _render_search_form():
    """Render the keyword-search form inside an ``st.form`` so that
    widget changes do not trigger reruns until the user submits."""
    with st.form(key=ui_key("search", "form"), border=True):
        # --- Row 1: keywords ---
        keywords = st.text_input(
            "检索关键词",
            value=st.session_state.get("search_keyword", ""),
            placeholder="输入英文关键词，使用 OR / AND / 引号组合，例如: PROTAC OR \"molecular glue\"",
            key="search_keyword",
        )

        # --- Row 2: sources + max_results ---
        c1, c2 = st.columns([3, 1])
        with c1:
            sources = st.multiselect(
                "数据源",
                options=SEARCH_SOURCES,
                default=st.session_state.get("search_sources", ["openalex"]),
                key="search_sources",
            )
        with c2:
            max_results = st.number_input(
                "最大结果数",
                min_value=5, max_value=100,
                value=st.session_state.get("search_max_results", 20),
                step=5, key="search_max_results",
            )

        # --- Row 3: year range + sort ---
        c3, c4, c5 = st.columns(3)
        with c3:
            year_from = st.number_input(
                "起始年份", min_value=1900, max_value=2030,
                value=st.session_state.get("search_year_from", 2020),
                key="search_year_from",
            )
        with c4:
            year_to = st.number_input(
                "结束年份", min_value=1900, max_value=2030,
                value=st.session_state.get("search_year_to", 2026),
                key="search_year_to",
            )
        with c5:
            sort_by = st.selectbox(
                "排序方式", options=SORT_OPTIONS,
                index=SORT_OPTIONS.index(st.session_state.get("search_sort_by", "relevance")),
                format_func=lambda x: SORT_LABELS[x],
                key="search_sort_by",
            )

        # --- Row 4: search mode + OA toggle ---
        c6, c7 = st.columns(2)
        with c6:
            search_mode_sel = st.selectbox(
                "检索策略", options=SEARCH_MODE_OPTIONS,
                index=0 if st.session_state.get("search_mode_sel", "backfill") == "backfill" else 1,
                format_func=lambda x: SEARCH_MODE_LABELS[x],
                key="search_mode_sel",
            )
        with c7:
            oa_only = st.checkbox(
                "仅 OA 文献",
                value=st.session_state.get("search_oa_only", False),
                key="search_oa_only",
            )

        # --- Submit ---
        submitted = st.form_submit_button(
            "开始检索",
            type="primary",
            use_container_width=True,
        )

        if submitted:
            if not keywords.strip():
                st.warning("请输入检索关键词。")
            else:
                _execute_search(
                    keywords, sources, year_from, year_to, max_results,
                    sort_by, oa_only,
                    st.session_state.get("search_nsc_boost", False),
                    search_mode_sel,
                )


# ============================================================================
# Region 4 — Advanced settings (collapsed)
# ============================================================================

def _render_advanced_settings():
    """NSC boost, journal-watch info, data-source notes."""
    with st.expander("高级检索设置", expanded=False):
        nsc_boost = st.checkbox(
            "顶刊强化 (Nature / Science / Cell / PNAS)",
            value=st.session_state.get("search_nsc_boost", False),
            help="在检索式中追加 AND (Nature OR Science OR Cell OR PNAS)，缩小范围至顶刊。",
            key="search_nsc_boost",
        )

        st.divider()
        st.caption("**检索策略说明**")
        st.caption("- **批量回填**：优先 OpenAlex，适合初次大面积检索某个领域。")
        st.caption("- **日常监控**：优先 Crossref / PubMed，适合跟踪最新发表。")

        st.caption("**数据源说明**")
        st.caption("- OpenAlex — 覆盖面广，免费无限制")
        st.caption("- Crossref — DOI 注册中心，元数据权威")
        st.caption("- PubMed — 生物医学首选，MeSH 索引")
        st.caption("- Europe PMC — 生命科学补充，OA 全文多")

        st.caption("**限速提示**：单次最多返回 100 条，建议先用宽泛词回填，再用精确词缩小。")


# ============================================================================
# Region 5 — Result statistics
# ============================================================================

def _render_result_stats(results, total_count, errors):
    """Show summary metric cards above the results table."""
    if not results:
        return

    oa_count = len([p for p in results if p.get("oa_status") in ("gold", "green", "hybrid", "bronze")])
    cited = len([p for p in results if p.get("citation_count", 0) > 0])
    valid_years = [p["year"] for p in results if p.get("year")]
    avg_year = sum(valid_years) / max(len(valid_years), 1) if valid_years else 0
    sources_used = {p.get("source", "") for p in results}

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.metric("返回文献", len(results))
    with c2:
        st.metric("OA 可获取", oa_count)
    with c3:
        st.metric("有引用", cited)
    with c4:
        st.metric("平均年份", f"{avg_year:.1f}")
    with c5:
        st.metric("数据源数", len(sources_used))
    with c6:
        st.metric("错误数", len(errors) if errors else 0)

    if errors:
        with st.expander(f"检索警告 ({len(errors)})"):
            for err in errors:
                st.warning(err)


# ============================================================================
# Region 6 & 7 — Result table + paper detail
# ============================================================================

def _render_results_table_and_detail(results):
    """Show the results table and, when a paper is selected, its full detail."""
    if not results:
        return

    render_divider()
    render_section("检索结果")

    # Build table data + selection labels
    table_data = []
    selection_labels = []
    for i, paper in enumerate(results):
        idx = i + 1
        title = paper.get("title", "")
        short_title = title[:80] + "..." if len(title) > 80 else title
        selection_labels.append(f"第 {idx} 篇 — {short_title}")

        table_data.append({
            "序号": idx,
            "标题": title[:100] + "..." if len(title) > 100 else title,
            "年份": paper.get("year") or "—",
            "期刊": (paper.get("journal") or "—")[:30],
            "DOI": paper.get("doi") or "—",
            "来源": paper.get("source", "—"),
            "OA": paper.get("oa_status", "—"),
            "引用": paper.get("citation_count", 0),
        })

    render_paper_table(table_data, column_config={
        "序号": st.column_config.NumberColumn(width="small"),
        "标题": st.column_config.TextColumn(width="large"),
        "年份": st.column_config.NumberColumn(width="small"),
        "期刊": st.column_config.TextColumn(width="medium"),
        "DOI": st.column_config.TextColumn(width="small"),
        "来源": st.column_config.TextColumn(width="small"),
        "OA": st.column_config.TextColumn(width="small"),
        "引用": st.column_config.NumberColumn(width="small"),
    })

    # Paper selector — guard against stale session_state returning None
    label_to_idx: dict[str, int] = {label: i for i, label in enumerate(selection_labels)}
    options = ["—"] + selection_labels
    selected_label = st.selectbox(
        "选择文献查看详情",
        options=options,
        key=ui_key("search", "paper_selector"),
    )

    if selected_label and selected_label != "—":
        idx = label_to_idx.get(selected_label, 0)
        paper = results[idx]
        _render_paper_detail(paper, idx)


def _render_paper_detail(paper: dict, idx: int):
    """Show a single paper's full metadata."""
    with st.expander(f"文献详情: {(paper.get('title') or '')[:60]}...", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**标题**: {paper.get('title', '—')}")
            st.markdown(f"**DOI**: `{paper.get('doi') or '—'}`")
            st.markdown(f"**期刊**: {paper.get('journal') or '—'}")
            st.markdown(f"**年份**: {paper.get('year') or '—'}")
            st.markdown(f"**来源**: {paper.get('source') or '—'}")
        with c2:
            st.markdown(f"**OA 状态**: {paper.get('oa_status') or '—'}")
            st.markdown(f"**引用数**: {paper.get('citation_count', 0)}")
            authors = paper.get("authors", "")
            st.markdown(f"**作者**: {authors if authors else '—'}")

        abstract = paper.get("abstract")
        if abstract:
            with st.expander("摘要"):
                st.markdown(abstract)

        # Quick actions
        ca1, ca2, _ = st.columns([1, 1, 2])
        with ca1:
            if st.button("加入全文获取队列", key=ui_key("search", "queue_ft", idx),
                         use_container_width=True):
                st.session_state["fulltext_target_paper_id"] = idx + 1
                title = paper.get("title", "")[:40]
                set_page_message("info", f"《{title}》已加入全文获取队列，请切换到「全文获取 / PDF 下载」页面操作。")
                st.rerun()
        with ca2:
            doi = paper.get("doi")
            if doi:
                st.code(doi, language=None)


# ============================================================================
# Region 8 — Action bar
# ============================================================================

def _render_action_bar():
    """Restore last search / clear results buttons."""
    render_divider()
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        if st.button("恢复最近检索结果", key=ui_key("search", "restore_btn"), use_container_width=True):
            _restore_last_search()
    with c2:
        if st.button("清空检索结果", key=ui_key("search", "clear_btn"), use_container_width=True):
            clear_search_state()
            set_page_message("info", "检索结果已清空。")
            st.rerun()
    with c3:
        if st.button("刷新数据", key=ui_key("search", "refresh"), use_container_width=True):
            st.rerun()


# ============================================================================
# Search execution
# ============================================================================

def _execute_search(keywords, sources, year_from, year_to, max_results, sort_by, oa_only, nsc_boost, search_mode):
    """Execute keyword search and store results in session_state."""
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

        result = execute_keyword_search(params)
        if result["success"]:
            data = result["data"]
            st.session_state["search_results"] = data["papers"]
            st.session_state["search_total_count"] = data["total_count"]
            st.session_state["search_errors"] = data["errors"]
            st.session_state["last_search_query"] = data["last_query"]
            st.session_state["search_last_stats"] = {
                "total_count": data["total_count"],
                "error_count": len(data.get("errors", [])),
                "sources_used": sources,
            }
            status.update(label=result["message"], state="complete")
        else:
            status.update(label="检索失败", state="error")
            st.error(f"检索过程中发生错误: {result['error']}")
            st.session_state["search_results"] = None
            st.session_state["search_total_count"] = 0
            st.session_state["search_errors"] = [result["error"]]
            st.session_state["search_last_stats"] = None


def _restore_last_search():
    """Restore most recent search from database."""
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
                "keywords": run_dict.get("query_keywords", ""),
                "sources": run_dict.get("sources_used", "").split(",") if run_dict.get("sources_used") else [],
                "year_from": None, "year_to": None,
                "max_results": run_dict.get("total_found", 0),
            }
            st.session_state["search_last_stats"] = {
                "total_count": len(papers),
                "error_count": 0,
                "sources_used": run_dict.get("sources_used", "").split(","),
            }
            set_page_message("success", f"已恢复最近检索结果: {len(papers)} 篇论文")
        else:
            set_page_message("warning", "数据库中未找到论文记录。")
    else:
        set_page_message("info", result["message"])
    st.rerun()


# ============================================================================
# Journal watch (unchanged from Step 5)
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
        _render_template_chips()
        _render_search_form()
        _render_advanced_settings()

        results = st.session_state.get("search_results")
        errors = st.session_state.get("search_errors", [])
        total_count = st.session_state.get("search_total_count", 0)

        if results:
            _render_result_stats(results, total_count, errors)
            _render_results_table_and_detail(results)

        _render_action_bar()

        # Show query details if available
        last_query = st.session_state.get("last_search_query")
        if last_query and results:
            with st.expander("查询详情"):
                st.json(last_query)
    else:
        _render_journal_watch()
