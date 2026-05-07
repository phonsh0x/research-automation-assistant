"""
Streamlit 交互界面 — 科研自动化助手前端。

启动方式：
  streamlit run ui/app.py

页面导航（侧边栏）：
  - 首页 / 系统概览
  - 文献检索
  - 我的文献库
  - PDF 转换
  - RAG 智能问答
  - 课题组画像
  - 写作辅助
  - 系统设置
"""

import sys
from pathlib import Path

# 将项目根目录添加到 Python 路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

# ============================================================================
# 页面配置（必须是第一个 Streamlit 命令）
# ============================================================================
st.set_page_config(
    page_title="科研自动化助手",
    page_icon=":books:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
# 侧边栏导航
# ============================================================================
with st.sidebar:
    st.title(":books: 科研自动化助手")
    st.caption("课题组文献管理与科研辅助系统")
    st.divider()

    # 导航菜单
    page = st.radio(
        "导航",
        options=[
            "首页 — 系统概览",
            "文献检索",
            "我的文献库",
            "全文获取 / PDF 下载",
            "PDF 转换",
            "RAG 智能问答",
            "课题组画像",
            "写作辅助",
            "系统设置",
        ],
        index=0,
    )

    st.divider()
    st.caption(f"版本: 0.1.0 (Phase 1)")
    st.caption("基于 DeepSeek-V4-Pro")


# ============================================================================
# 文献检索辅助函数（定义在模块级别，页面路由之前）
# ============================================================================

def _render_keyword_search():
    """渲染关键词检索页面。"""
    # 药物化学关键词模板
    with st.expander("药物化学关键词模板（点击展开）"):
        col_t1, col_t2, col_t3 = st.columns(3)
        templates = {
            "靶向蛋白降解 (PROTAC/分子胶)": 'PROTAC OR "molecular glue" OR "targeted protein degradation"',
            "共价抑制剂": '"covalent inhibitor" OR "irreversible inhibitor" OR "targeted covalent inhibitor"',
            "变构调节剂": '"allosteric modulator" OR "allosteric inhibitor" OR "allosteric regulation"',
            "AI 驱动的药物发现": '"AI-driven drug discovery" OR "machine learning drug design" OR "deep learning drug discovery"',
            "基于片段的药物设计 FBDD": '"fragment-based drug design" OR FBDD OR "fragment screening"',
            "抗肿瘤药物": 'anticancer OR antitumor OR "cancer drug discovery"',
            "天然产物药物化学": '"natural product" AND "drug discovery" OR "natural product chemistry"',
            "先导化合物优化": '"lead optimization" OR "lead compound" AND "medicinal chemistry"',
        }
        with col_t1:
            for i, (label, template) in enumerate(list(templates.items())[:3]):
                if st.button(label, key=f"tpl_{i}", use_container_width=True):
                    st.session_state["keywords_input"] = template
        with col_t2:
            for i, (label, template) in enumerate(list(templates.items())[3:6]):
                if st.button(label, key=f"tpl_{i+3}", use_container_width=True):
                    st.session_state["keywords_input"] = template
        with col_t3:
            for i, (label, template) in enumerate(list(templates.items())[6:]):
                if st.button(label, key=f"tpl_{i+6}", use_container_width=True):
                    st.session_state["keywords_input"] = template

    # 检索参数
    col1, col2 = st.columns([3, 1])
    with col1:
        if "keywords_input" not in st.session_state:
            st.session_state["keywords_input"] = ""
        keywords = st.text_input(
            "检索关键词",
            value=st.session_state["keywords_input"],
            placeholder="例如: deep learning medical image segmentation",
            key="kw_input",
        )
    with col2:
        max_results = st.number_input("最大结果数", min_value=5, max_value=100, value=20, step=5)

    col3, col4, col5 = st.columns(3)
    with col3:
        year_from = st.number_input("起始年份", min_value=1900, max_value=2030, value=2020)
    with col4:
        year_to = st.number_input("结束年份", min_value=1900, max_value=2030, value=2026)
    with col5:
        sources = st.multiselect(
            "数据源",
            options=["openalex", "crossref", "pubmed", "europe_pmc"],
            default=["openalex"],
        )

    # 进阶选项
    with st.expander("进阶选项"):
        col_a, col_b = st.columns(2)
        with col_a:
            nsc_boost = st.checkbox(
                "顶刊强化 (Nature/Science/Cell/PNAS)",
                value=False,
                help="开启后在关键词中追加 AND (Nature OR Science OR Cell OR PNAS) 过滤",
            )
            oa_only = st.checkbox("仅 OA 文献", value=False)
        with col_b:
            sort_by = st.selectbox(
                "排序方式",
                options=["relevance", "year", "citations"],
                index=0,
                format_func=lambda x: {"relevance": "相关度", "year": "年份", "citations": "引用数"}[x],
            )
            search_mode_sel = st.selectbox(
                "检索策略",
                options=["backfill", "daily_watch"],
                index=0,
                format_func=lambda x: {"backfill": "批量回填 (优先 OpenAlex)", "daily_watch": "日常监控 (优先 Crossref/PubMed)"}[x],
            )

    if st.button("开始检索 (关键词)", type="primary", use_container_width=True):
        if not keywords:
            st.warning("请输入检索关键词。")
        else:
            _execute_search(keywords, sources, year_from, year_to, max_results, sort_by, oa_only, nsc_boost, search_mode_sel)


def _execute_search(keywords, sources, year_from, year_to, max_results, sort_by, oa_only, nsc_boost, search_mode):
    """执行文献检索并展示结果。"""
    from src.paper_search.models import SearchQuery
    from src.paper_search.searcher import PaperSearcher

    # 顶刊强化
    final_keywords = keywords
    if nsc_boost:
        final_keywords = f"({keywords}) AND (Nature OR Science OR Cell OR PNAS)"

    query = SearchQuery(
        keywords=final_keywords,
        max_results=max_results,
        year_from=year_from if year_from > 1900 else None,
        year_to=year_to if year_to < 2030 else None,
        sources=sources,
        sort_by=sort_by,
        filter_oa_only=oa_only,
    )

    with st.status(f"正在检索: '{final_keywords}' ...", expanded=True) as status:
        st.write(f"关键词: {final_keywords}")
        st.write(f"数据源: {', '.join(sources)}")
        st.write(f"年份: {year_from} - {year_to}")
        st.write(f"排序: {sort_by}")

        try:
            searcher = PaperSearcher()
            result = searcher.search(query)
            status.update(label=f"检索完成，找到 {result.total_count} 篇论文", state="complete")

            if result.errors:
                for err in result.errors:
                    st.warning(err)

        except Exception as e:
            status.update(label="检索失败", state="error")
            st.error(f"检索过程中发生错误: {e}")
            return

    # 展示结果
    if result.papers:
        st.success(f"共找到 {result.total_count} 篇论文，显示 {len(result.papers)} 条")

        # 统计信息
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        oa_count = len([p for p in result.papers if p.oa_status in ("gold", "green", "hybrid", "bronze")])
        with col_s1:
            st.metric("总计", len(result.papers))
        with col_s2:
            st.metric("OA 可获取", oa_count)
        with col_s3:
            valid_years = [p.year for p in result.papers if p.year]
            avg_year = sum(valid_years) / max(len(valid_years), 1)
            st.metric("平均年份", f"{avg_year:.1f}")
        with col_s4:
            cited = len([p for p in result.papers if p.citation_count > 0])
            st.metric("有引用", cited)

        # 表格
        table_data = []
        for i, paper in enumerate(result.papers, start=1):
            authors_str = ", ".join(paper.authors[:3])
            if len(paper.authors) > 3:
                authors_str += " 等"
            table_data.append({
                "序号": i,
                "标题": paper.title[:100] + "..." if len(paper.title) > 100 else paper.title,
                "第一作者": paper.authors[0] if paper.authors else "未知",
                "年份": paper.year if paper.year else "未知",
                "期刊": paper.journal if paper.journal else "未知",
                "OA": paper.oa_status,
                "引用": paper.citation_count,
                "来源": paper.source_api,
            })

        st.dataframe(
            table_data,
            use_container_width=True,
            column_config={
                "序号": st.column_config.NumberColumn(width="small"),
                "标题": st.column_config.TextColumn(width="large"),
                "OA": st.column_config.TextColumn(width="small"),
                "引用": st.column_config.NumberColumn(width="small"),
            },
        )
    else:
        st.info("未找到匹配的论文。请尝试调整关键词或放宽条件。")


def _render_journal_watch():
    """渲染重点期刊监控页面。"""
    from src.paper_search.journal_watchlist import JournalWatchlist

    wl = JournalWatchlist()

    # 期刊清单
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
            st.dataframe(journal_data, use_container_width=True)
        else:
            st.warning("期刊清单为空，请先初始化数据库。")

    # 监控设置
    st.divider()
    col_d1, col_d2 = st.columns([2, 1])
    with col_d1:
        days = st.selectbox("监控最近天数", options=[1, 3, 7, 14, 30], index=2)
    with col_d2:
        active_only = st.checkbox("仅活跃期刊", value=True)

    if st.button("开始监控 (期刊)", type="primary", use_container_width=True):
        _execute_journal_watch(wl, days, active_only)


def _execute_journal_watch(wl, days, active_only):
    """执行期刊监控并展示结果。"""
    from src.paper_search.rss_watcher import run_rss_watch
    from src.paper_search.aggregator import SearchAggregator
    from src.paper_search.openalex import OpenAlexSearcher
    from src.storage.repository import PaperRepository

    journals = wl.get_journals(active_only=active_only)
    rss_urls = [j["rss_url"] for j in journals if j.get("rss_url")]
    journal_names = [j["name"] for j in journals if j.get("rss_url")]

    with st.status(f"期刊监控中（最近 {days} 天）...", expanded=True) as status:
        all_papers = []

        # 1. RSS 抓取
        if rss_urls:
            st.write(f"正在抓取 {len(rss_urls)} 个 RSS 源...")
            try:
                rss_papers = run_rss_watch(rss_urls, journal_names, days=days)
                st.write(f"RSS 获取: {len(rss_papers)} 篇")
                all_papers.extend(rss_papers)
            except Exception as e:
                st.warning(f"RSS 抓取异常: {e}")

        # 2. API 补充检索
        search_journals = [j["name"] for j in journals if not j.get("rss_url")]
        if search_journals:
            st.write(f"正在通过 API 检索 {len(search_journals)} 个期刊...")
            searcher = OpenAlexSearcher()
            for jname in search_journals[:5]:
                try:
                    papers = searcher.get_recent(jname, days=days)
                    all_papers.extend(papers)
                except Exception as e:
                    st.warning(f"检索 {jname} 失败: {e}")

        # 3. 去重 & 入库
        if all_papers:
            agg = SearchAggregator(searchers=[], repository=PaperRepository())
            deduped = agg.deduplicate(all_papers)
            st.write(f"去重后: {len(deduped)} 篇")
            new_count = agg.save_results(deduped)
            st.write(f"新增入库: {new_count} 篇")

            agg.record_search_run(
                run_type="daily_watch",
                sources=["rss", "openalex"],
                keywords=f"期刊监控 ({days}天)",
                total_found=len(deduped),
                new_added=new_count,
            )

            status.update(label=f"监控完成，共 {len(deduped)} 篇（新增 {new_count} 篇）", state="complete")
            st.success(f"共发现 {len(deduped)} 篇新论文，其中 {new_count} 篇已入库。")
        else:
            status.update(label="监控完成，未发现新论文", state="complete")
            st.info("最近未发现新论文。")


# ============================================================================
# 页面路由
# ============================================================================

# --- 首页 ---
if page == "首页 — 系统概览":
    st.title("系统概览")
    st.markdown("""
    ### 欢迎使用课题组科研自动化助手

    本系统覆盖学术研究的全链路，帮助课题组高效管理文献和辅助科研写作。

    #### 当前阶段: Phase 1 — 基础功能

    | 功能模块 | 状态 | 说明 |
    |---------|------|------|
    | 文献检索 | 框架就绪 | 通过 OpenAlex/Crossref/PubMed/arXiv 检索文献 |
    | 全文下载 | 框架就绪 | 通过 Unpaywall 等合法 API 获取开放获取 PDF |
    | 入库管理 | 框架就绪 | SQLite 数据库存储和管理文献元数据 |
    | PDF 转换 | Phase 2 | 学术 PDF 转结构化 Markdown |
    | RAG 问答 | Phase 2 | 基于本地文献库的智能问答 |
    | 课题组画像 | Phase 3 | 研究方向分析和合作网络 |
    | 写作辅助 | Phase 3 | 文献综述和基金申请书辅助 |

    #### 快速开始

    1. 在侧边栏选择"文献检索"，尝试检索论文
    2. 在"系统设置"中配置 API Key 等参数
    3. 下载论文 PDF 后，可通过"PDF 转换"转为 Markdown
    4. 使用"RAG 智能问答"基于本地文献库提问

    #### 法律声明

    本系统仅通过合法开放 API 获取文献全文（OpenAlex、Crossref、PubMed、arXiv、Unpaywall 等），
    严禁使用 Sci-Hub 或任何绕过付费墙的手段。
    """)

    # 快速状态卡片
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="本地论文数", value="0", delta="Phase 1")
    with col2:
        st.metric(label="已下载 PDF", value="0")
    with col3:
        st.metric(label="已转 Markdown", value="0")
    with col4:
        st.metric(label="向量索引块", value="0")

# --- 文献检索 ---
elif page == "文献检索":
    st.title("文献检索")
    st.markdown("通过合法开放 API 检索学术论文。")

    # 检索模式选择
    search_mode = st.radio(
        "检索模式",
        options=["按关键词检索", "重点期刊监控"],
        horizontal=True,
    )

    if search_mode == "按关键词检索":
        _render_keyword_search()
    else:
        _render_journal_watch()
# --- 我的文献库 ---
elif page == "我的文献库":
    st.title("我的文献库")
    st.markdown("管理已入库的论文。")

    tab1, tab2 = st.tabs(["论文列表", "导入/导出"])

    with tab1:
        st.info("本地文献库功能框架已就绪。论文列表查询功能将在 Phase 1 中实现。")
        st.dataframe(
            [],
            use_container_width=True,
        )

    with tab2:
        st.markdown("#### 导入文献")
        uploaded_file = st.file_uploader(
            "上传 BibTeX 或 CSV 文件",
            type=["bib", "csv", "json"],
        )
        if uploaded_file:
            st.info("文件导入功能将在 Phase 1 中实现。")

        st.markdown("#### 导出文献")
        export_format = st.selectbox("导出格式", ["BibTeX", "CSV", "JSON"])
        if st.button("导出全部论文"):
            st.info(f"{export_format} 导出功能将在 Phase 1 中实现。")

# --- 全文获取 / PDF 下载 ---
elif page == "全文获取 / PDF 下载":
    st.title("全文获取 / PDF 下载")
    st.markdown("通过合法开放 API 获取学术论文 PDF 全文。")

    # 统计卡片
    try:
        from src.storage.repository import PaperRepository
        repo = PaperRepository()
        stats = repo.get_download_statistics()
    except Exception:
        stats = {}

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("论文总数", stats.get("total_papers", 0))
    with col2:
        st.metric("已有 PDF", stats.get("with_pdf", 0))
    with col3:
        st.metric("待获取", stats.get("without_pdf", 0))
    with col4:
        st.metric("需人工审查", stats.get("manual_review", 0))
    with col5:
        st.metric("失败", stats.get("failed", 0))

    st.divider()

    # 来源分布和法律状态
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### 按来源分布")
        by_source = stats.get("by_source", {})
        if by_source:
            st.dataframe(
                [{"来源": k, "数量": v} for k, v in by_source.items()],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("暂无数据")
    with col_b:
        st.markdown("#### 按法律状态分布")
        by_legal = stats.get("by_legal_status", {})
        if by_legal:
            st.dataframe(
                [{"法律状态": k, "数量": v} for k, v in by_legal.items()],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("暂无数据")

    st.divider()

    # 待下载论文列表
    st.markdown("### 待获取全文的论文")

    col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
    with col_f1:
        pending_limit = st.selectbox("显示数量", options=[10, 20, 50, 100], index=1)
    with col_f2:
        st.caption("")
        st.caption("")
        refresh_btn = st.button("刷新列表", use_container_width=True)
    with col_f3:
        st.caption("")
        st.caption("")
        batch_download_btn = st.button("批量获取 (前10篇)", type="primary", use_container_width=True)

    try:
        repo2 = PaperRepository()
        pending_papers = repo2.get_papers_without_pdf(limit=pending_limit)
    except Exception:
        pending_papers = []

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

        st.dataframe(
            pending_data,
            use_container_width=True,
            column_config={
                "ID": st.column_config.NumberColumn(width="small"),
                "标题": st.column_config.TextColumn(width="large"),
                "DOI": st.column_config.TextColumn(width="medium"),
                "OA状态": st.column_config.TextColumn(width="small"),
            },
        )

        # 单篇操作
        st.markdown("#### 单篇操作")
        col_op1, col_op2, col_op3 = st.columns([1, 1, 2])
        with col_op1:
            target_paper_id = st.number_input("论文 ID", min_value=1, step=1, value=1)
        with col_op2:
            st.caption("")
            resolve_btn = st.button("查询来源", use_container_width=True)
        with col_op3:
            st.caption("")
            col_dl, col_mr = st.columns(2)
            with col_dl:
                download_btn = st.button("下载全文", type="primary", use_container_width=True)
            with col_mr:
                mark_review_btn = st.button("标记人工审查", use_container_width=True)

        if resolve_btn:
            with st.status(f"正在查询论文 {target_paper_id} 的全文来源...", expanded=True) as status:
                try:
                    from src.fulltext.service import FullTextAcquisitionService
                    service = FullTextAcquisitionService()
                    result = service.resolve(target_paper_id)
                    if result.pdf_url:
                        st.success(f"找到可用来源: {result.source} — {result.pdf_url[:100]}...")
                    else:
                        st.warning(f"未找到可用全文: {result.error_message or '所有来源均不可用'}")
                    status.update(label="查询完成", state="complete")
                except Exception as e:
                    st.error(f"查询失败: {e}")
                    status.update(label="查询失败", state="error")

        if download_btn:
            with st.status(f"正在获取论文 {target_paper_id} 全文...", expanded=True) as status:
                try:
                    from src.fulltext.service import FullTextAcquisitionService
                    service = FullTextAcquisitionService()
                    result = service.download(target_paper_id)
                    if result.pdf_path:
                        st.success(f"PDF 下载成功: {result.pdf_path} ({result.file_size} 字节)")
                        status.update(label="下载完成", state="complete")
                    else:
                        st.warning(f"获取失败: {result.error_message}")
                        status.update(label="获取失败", state="error")
                except Exception as e:
                    st.error(f"下载失败: {e}")
                    status.update(label="失败", state="error")

        if mark_review_btn:
            try:
                success = repo2.mark_manual_review(target_paper_id, "用户在 UI 中标记为需人工审查")
                if success:
                    st.success(f"论文 {target_paper_id} 已标记为人工审查")
                else:
                    st.error(f"更新失败")
            except Exception as e:
                st.error(f"操作失败: {e}")

        if batch_download_btn:
            with st.status("正在批量获取全文...", expanded=True) as status:
                try:
                    from src.fulltext.service import FullTextAcquisitionService
                    service = FullTextAcquisitionService()
                    pending_ids = [p["paper_id"] for p in pending_papers[:10]]
                    results = service.batch_download(pending_ids)
                    success_count = len([r for r in results if r.pdf_path])
                    st.write(f"批量获取完成: 成功 {success_count}/{len(results)}")
                    for r in results:
                        if r.pdf_path:
                            st.write(f"- {r.paper_id}: {r.source} — 已下载")
                        else:
                            st.write(f"- {r.paper_id}: 失败 — {r.error_message}")
                    status.update(label=f"批量获取完成: {success_count}/{len(results)} 成功", state="complete")
                except Exception as e:
                    st.error(f"批量获取失败: {e}")
                    status.update(label="批量获取失败", state="error")
    else:
        st.info("所有论文均已有 PDF，无需获取。")

    st.divider()

    # 人工上传
    st.markdown("### 人工上传 PDF")
    st.caption("用于用户从机构网络或其他合法途径获得的 PDF 文件。请确认版权合规。")

    col_u1, col_u2 = st.columns([1, 1])
    with col_u1:
        upload_paper_id = st.number_input("论文 ID（上传）", min_value=1, step=1, key="upload_pid")
    with col_u2:
        upload_file = st.file_uploader("选择 PDF 文件", type=["pdf"])

    if upload_file and upload_paper_id:
        if st.button("上传并关联", type="primary"):
            try:
                from pathlib import Path
                import tempfile
                from src.fulltext.manual_upload import ManualUploadResolver

                paper = repo2.get_paper_by_id(upload_paper_id)
                if not paper:
                    st.error(f"论文 ID {upload_paper_id} 不存在")
                else:
                    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                        tmp.write(upload_file.read())
                        tmp_path = tmp.name

                    resolver = ManualUploadResolver()
                    result = resolver.upload(paper, tmp_path, user_confirmed_rights=True)

                    if result.pdf_path:
                        repo2.update_paper_pdf_status(
                            paper_id=upload_paper_id,
                            pdf_path=result.pdf_path,
                            download_status="downloaded",
                            access_source="manual_upload",
                            legal_status=result.legal_status,
                        )
                        repo2.record_fulltext_access(
                            paper_id=upload_paper_id,
                            doi=paper.get("doi", ""),
                            title=paper.get("title", ""),
                            access_status="manual_upload",
                            access_source="manual_upload",
                            access_mode="manual",
                            legal_status=result.legal_status,
                            pdf_path=result.pdf_path,
                            file_size=result.file_size,
                            checksum_sha256=result.checksum_sha256,
                            risk_level=result.risk_level,
                            risk_note=result.risk_note,
                        )
                        st.success(f"PDF 已上传: {result.pdf_path} ({result.file_size} 字节)")
                        Path(tmp_path).unlink(missing_ok=True)
                    else:
                        st.error(f"上传失败: {result.error_message}")
                        Path(tmp_path).unlink(missing_ok=True)
            except Exception as e:
                st.error(f"上传处理异常: {e}")

    st.divider()

    # 法律声明
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

# --- PDF 转换 ---
elif page == "PDF 转换":
    st.title("PDF 转 Markdown")
    st.markdown("将学术 PDF 论文转换为结构化 Markdown。")

    st.info("PDF 转换功能将在 Phase 2 中实现。转换引擎支持 marker, pymupdf, nougat。")

    uploaded_pdf = st.file_uploader("上传 PDF 文件", type=["pdf"])
    if uploaded_pdf:
        st.info("PDF 上传成功，但转换功能尚未实现。")

# --- RAG 智能问答 ---
elif page == "RAG 智能问答":
    st.title("RAG 智能问答")
    st.markdown("基于本地文献库的检索增强生成问答。")

    st.info("RAG 问答功能将在 Phase 2 中实现。回答将基于本地已入库文献生成。")

    question = st.text_area("请输入您的问题", placeholder="例如: U-Net 架构在医学图像分割中有哪些改进变体？")
    col1, col2 = st.columns([1, 5])
    with col1:
        submit = st.button("提交问题", type="primary")

    if submit and question:
        st.info(f"问题已收到: '{question[:80]}...'。RAG 问答将在 Phase 2 实现。")

# --- 课题组画像 ---
elif page == "课题组画像":
    st.title("课题组画像")
    st.markdown("分析课题组已发表论文，生成研究方向画像。")

    st.info("课题组画像功能将在 Phase 3 中实现。")
    st.markdown("""
    #### 即将支持的功能
    - 研究方向自动抽取
    - 关键词云和主题演化趋势
    - 合作者网络可视化
    - Markdown 分析报告
    """)

# --- 写作辅助 ---
elif page == "写作辅助":
    st.title("写作辅助")
    st.markdown("中文学术写作助手，辅助撰写文献综述、基金申请书和学术论文。")

    st.info("写作辅助功能将在 Phase 3 中实现。")

    writing_type = st.selectbox(
        "写作类型",
        ["文献综述", "基金申请书-立项依据", "学术论文摘要", "方法描述", "文字润色"],
    )

    text_input = st.text_area(
        "输入写作主题或待润色文本",
        placeholder="请输入写作主题或待润色的文本...",
        height=150,
    )

    if st.button("生成/润色", type="primary"):
        if text_input:
            st.info(f"写作辅助请求已收到: '{writing_type}'。功能将在 Phase 3 实现。")

# --- 系统设置 ---
elif page == "系统设置":
    st.title("系统设置")
    st.markdown("配置系统参数和 API 密钥。")

    tab1, tab2, tab3 = st.tabs(["API 配置", "系统参数", "关于"])

    with tab1:
        st.markdown("#### API 密钥配置")
        st.info("API 密钥的配置界面将在后续版本中完善。请在 config/.env 文件中手动配置。")

        st.code(
            "# 编辑 config/.env 文件，填入 API 密钥\n"
            'PAPER_ASSIST_LLM_API_KEY=your-deepseek-api-key-here\n'
            'PAPER_ASSIST_CONTACT_EMAIL=your-email@institution.edu\n',
            language="bash",
        )

    with tab2:
        st.markdown("#### 系统参数")
        st.info("系统参数从 config/default.yaml 读取，可通过环境变量覆盖（前缀 PAPER_ASSIST_）。")

        st.json({
            "数据库路径": "data/paper.db",
            "PDF 目录": "data/pdf/",
            "Markdown 目录": "data/markdown/",
            "向量库路径": "data/vector_db/",
            "日志目录": "data/logs/",
            "日志级别": "INFO",
        })

    with tab3:
        st.markdown("""
        #### 关于本系统

        **课题组科研自动化助手** v0.1.0

        技术栈:
        - **后端**: Python + FastAPI
        - **前端**: Streamlit
        - **数据库**: SQLite
        - **向量库**: ChromaDB
        - **LLM**: DeepSeek-V4-Pro
        - **文献检索**: OpenAlex, Crossref, PubMed, arXiv

        #### 合法获取文献

        所有文献获取均通过合法开放 API，严禁使用 Sci-Hub 或任何绕过付费墙的手段。

        #### 开发路线

        - **Phase 1** (基础): 检索 + 下载 + 入库
        - **Phase 2** (智能): PDF 转换 + RAG 问答
        - **Phase 3** (进阶): 课题组画像 + 写作辅助 + Web UI
        """)


# ============================================================================
# 页脚
# ============================================================================
st.sidebar.divider()
st.sidebar.caption("2026 课题组科研自动化助手")
