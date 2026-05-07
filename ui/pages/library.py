"""Library page — search, filter, and export papers from the local repository."""

import streamlit as st

from ui.state import ui_key
from ui.constants import (
    LIBRARY_SOURCE_FILTERS,
    LIBRARY_DISPLAY_COUNTS,
    EXPORT_FORMATS,
)
from ui.components.layout import render_page_header, render_empty_state
from ui.components.paper_table import render_paper_table
from ui.components.messages import render_page_message
from ui.services.repository_service import search_library
from ui.services.export_service import export_bibtex


def render():
    render_page_header("我的文献库", "管理已入库的论文。")
    render_page_message()

    tab1, tab2 = st.tabs(["论文列表", "导入/导出"], key=ui_key("library", "tabs"))

    with tab1:
        st.markdown("#### 搜索本地文献库")

        col_l1, col_l2 = st.columns([2, 1])
        with col_l1:
            library_keyword = st.text_input(
                "关键词搜索（标题/摘要/期刊）",
                value=st.session_state.get("library_keyword", ""),
                placeholder="输入关键词搜索已入库论文...",
                key="library_keyword",
            )
        with col_l2:
            library_limit = st.selectbox(
                "显示数量", options=LIBRARY_DISPLAY_COUNTS,
                index=[10, 20, 50, 100].index(st.session_state.get("library_limit", 20)),
                key="library_limit",
            )

        col_l3, col_l4, col_l5 = st.columns(3)
        with col_l3:
            library_source = st.selectbox(
                "数据源筛选", options=LIBRARY_SOURCE_FILTERS, index=0, key="library_source",
            )
        with col_l4:
            lib_year_from = st.number_input(
                "起始年份", min_value=1900, max_value=2030,
                value=st.session_state.get("library_year_from") or 1900,
                key="library_year_from",
            )
        with col_l5:
            lib_year_to = st.number_input(
                "结束年份", min_value=1900, max_value=2030,
                value=st.session_state.get("library_year_to") or 2030,
                key="library_year_to",
            )

        col_lb1, col_lb2 = st.columns([1, 4])
        with col_lb1:
            if st.button("搜索文献库", key=ui_key("library", "search_btn"), type="primary", use_container_width=True):
                source = None if library_source == "全部" else library_source
                yf = lib_year_from if lib_year_from > 1900 else None
                yt = lib_year_to if lib_year_to < 2030 else None
                result = search_library(
                    keyword=library_keyword or "", limit=library_limit, offset=0,
                    source=source, year_from=yf, year_to=yt,
                )
                if result["success"]:
                    papers = result["data"]["papers"]
                    st.session_state["library_results"] = papers
                    st.session_state["library_total_count"] = result["data"]["count"]
                    st.session_state["search_errors"] = []
                    if not papers:
                        render_empty_state("未找到", "没有匹配的论文。")
                else:
                    st.error(f"搜索失败: {result['error']}")

        with col_lb2:
            if st.button("清空筛选条件", key=ui_key("library", "clear_btn"), use_container_width=True):
                st.session_state["library_keyword"] = ""
                st.session_state["library_source"] = "全部"
                st.session_state["library_year_from"] = 1900
                st.session_state["library_year_to"] = 2030
                st.session_state["library_results"] = None
                st.rerun()

        results = st.session_state.get("library_results")
        if results:
            st.markdown(f"#### 共 {len(results)} 条结果")
            table_data = []
            for paper in results:
                title = paper.get("title") or ""
                table_data.append({
                    "ID": paper.get("id", ""),
                    "标题": title[:100] + "..." if len(title) > 100 else title,
                    "作者": (paper.get("authors") or "未知")[:50],
                    "年份": paper.get("year") or "",
                    "期刊": (paper.get("journal") or "")[:30],
                    "OA": paper.get("oa_status", ""),
                    "来源": paper.get("source", ""),
                    "入日期": (paper.get("created_at") or "")[:10],
                })
            render_paper_table(table_data, column_config={
                "ID": st.column_config.NumberColumn(width="small"),
                "标题": st.column_config.TextColumn(width="large"),
            })

    with tab2:
        st.markdown("#### 导入文献")
        uploaded_file = st.file_uploader(
            "上传 BibTeX 或 CSV 文件", type=["bib", "csv", "json"],
            key=ui_key("library", "import_file"),
        )
        if uploaded_file:
            st.info("文件导入功能将在后续版本中实现。")

        st.markdown("#### 导出文献")
        export_format = st.selectbox("导出格式", EXPORT_FORMATS, key=ui_key("library", "export_format"))
        if st.button("导出全部论文", key=ui_key("library", "export_btn")):
            result = export_bibtex()
            if result["success"] and result["data"]:
                st.download_button(
                    "下载 BibTeX", data=result["data"],
                    file_name="papers.bib", mime="text/plain",
                    key=ui_key("library", "download_bibtex"),
                )
            else:
                st.warning(result["message"] or "没有可导出的论文。")
