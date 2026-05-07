"""Settings page — API config, system parameters, about."""

import streamlit as st

from ui.state import ui_key
from ui.components.layout import render_page_header
from ui.components.messages import render_page_message


def render():
    render_page_header("系统设置", "配置系统参数和 API 密钥。")
    render_page_message()

    tab1, tab2, tab3 = st.tabs(["API 配置", "系统参数", "关于"], key=ui_key("settings", "tabs"))

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
            "Session State Keys": sorted([k for k in st.session_state.keys() if not k.startswith("_")]),
        })

    with tab3:
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
