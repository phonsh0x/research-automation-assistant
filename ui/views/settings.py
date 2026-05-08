"""Settings page — API config, system parameters, data source health, about."""

import streamlit as st

from ui.components.layout import render_page_header
from ui.components.messages import render_page_message


def _mask_key(value: str) -> str:
    """Mask an API key to show only first 3 and last 3 chars."""
    if not value:
        return "未配置"
    if len(value) <= 6:
        return value[:2] + "**"
    return value[:3] + "…" + value[-3:]


def render():
    render_page_header("系统设置", "配置系统参数、API 密钥和数据源。")
    render_page_message()

    tab1, tab2, tab3, tab4 = st.tabs(["API 配置", "数据源健康检查", "系统参数", "关于"])

    # ------------------------------------------------------------------
    # Tab 1 — API key configuration
    # ------------------------------------------------------------------
    with tab1:
        st.markdown("#### API 密钥配置")
        st.info("API 密钥请在 `config/.env` 文件中配置。系统启动时自动加载。")

        st.code(
            "# 编辑 config/.env 文件，填入 API 密钥\n"
            'PAPER_ASSIST_LLM_API_KEY=your-deepseek-api-key-here\n'
            'PAPER_ASSIST_CONTACT_EMAIL=your-email@institution.edu\n'
            'PAPER_ASSIST_OPENALEX_API_KEY=your-openalex-api-key-here\n'
            'PAPER_ASSIST_CROSSREF_MAILTO=your-email@institution.edu\n'
            'PAPER_ASSIST_NCBI_API_KEY=your-ncbi-api-key-here\n'
            'PAPER_ASSIST_UNPAYWALL_EMAIL=your-email@institution.edu\n',
            language="bash",
        )

    # ------------------------------------------------------------------
    # Tab 2 — Data source health
    # ------------------------------------------------------------------
    with tab2:
        st.markdown("#### 数据源配置与健康检查")
        st.caption("显示各数据源的配置状态和可用性。API key 不会明文展示。")

        from src.fulltext.source_health import SourceHealthChecker

        health = SourceHealthChecker.check_all()

        # Metadata sources
        st.markdown("##### 元数据检索源")
        meta_data = []
        for s in health["metadata"]:
            cfg = "已配置" if s["configured"] else ("未配置" if s["requires_key"] or s["requires_email"] else "免费开放")
            status_icon = "✅" if s["available"] else "❌"
            key_info = ""
            if s["requires_key"]:
                from src.config import get_config
                raw = ""
                if s["source"] == "OpenAlex":
                    raw = get_config("openalex.api_key", "")
                elif s["source"] == "Semantic Scholar":
                    raw = get_config("semantic_scholar.api_key", "")
                key_info = f" | Key: {_mask_key(raw)}"
            if s["requires_email"]:
                from src.config import get_config
                raw = ""
                if s["source"] == "Crossref":
                    raw = get_config("crossref.mailto", "")
                key_info = f" | Email: {_mask_key(raw)}"
            meta_data.append({
                "数据源": s["source"],
                "状态": f"{status_icon} {cfg}{key_info}",
                "用途": "元数据检索",
                "说明": s["message"],
            })

        if meta_data:
            st.dataframe(meta_data, use_container_width=True, hide_index=True)

        # Fulltext sources
        st.markdown("##### 全文获取源")
        ft_data = []
        for s in health["fulltext"]:
            cfg = "已配置" if s["configured"] else ("未配置" if s["requires_key"] or s["requires_email"] else "免费开放")
            status_icon = "✅" if s["available"] else "❌"
            key_info = ""
            if s["requires_email"] and s["source"] == "Unpaywall":
                from src.config import get_config
                raw = get_config("unpaywall.email", "")
                key_info = f" | Email: {_mask_key(raw)}"
            ft_data.append({
                "数据源": s["source"],
                "状态": f"{status_icon} {cfg}{key_info}",
                "用途": "全文获取",
                "说明": s["message"],
            })

        if ft_data:
            st.dataframe(ft_data, use_container_width=True, hide_index=True)

        st.divider()
        st.caption("提示：元数据检索源负责查找论文信息，全文获取源负责下载 PDF。两者缺一不可。")

    # ------------------------------------------------------------------
    # Tab 3 — System parameters
    # ------------------------------------------------------------------
    with tab3:
        st.markdown("#### 系统参数")
        st.info("系统参数从 config/default.yaml 读取，可通过环境变量覆盖（前缀 PAPER_ASSIST_）。")

        st.json({
            "数据库路径": "data/paper.db",
            "PDF 目录": "data/pdf/",
            "Markdown 目录": "data/markdown/",
            "向量库路径": "data/vector_db/",
            "日志目录": "data/logs/",
            "日志级别": "INFO",
            "Session State Keys": sorted([k for k in st.session_state.keys() if not k.startswith("_")]),
        })

    # ------------------------------------------------------------------
    # Tab 4 — About
    # ------------------------------------------------------------------
    with tab4:
        st.markdown("""
        #### 关于本系统

        **课题组科研自动化助手** v0.2.0

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
        - **Phase 1** (基础): 检索 + 下载 + 入库 ✅
        - **Phase 2** (智能): PDF 转换 + RAG 问答
        - **Phase 3** (进阶): 课题组画像 + 写作辅助 + Web UI
        """)
