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

    col1, col2 = st.columns([3, 1])

    with col1:
        keywords = st.text_input(
            "检索关键词",
            placeholder="例如: deep learning medical image segmentation",
        )
    with col2:
        max_results = st.number_input("最大结果数", min_value=5, max_value=100, value=20, step=5)

    col3, col4, col5 = st.columns(3)
    with col3:
        year_from = st.number_input("起始年份", min_value=1900, max_value=2030, value=2020)
    with col4:
        year_to = st.number_input("结束年份", min_value=1900, max_value=2030, value=2025)
    with col5:
        sources = st.multiselect(
            "数据源",
            options=["openalex", "crossref", "pubmed", "arxiv", "semantic_scholar"],
            default=["openalex"],
        )

    if st.button("开始检索", type="primary"):
        if not keywords:
            st.warning("请输入检索关键词。")
        else:
            st.info("检索功能框架已就绪。具体检索逻辑将在 Phase 1 实现中逐步添加。")
            st.info(f"查询参数: keywords='{keywords}', sources={sources}, year={year_from}-{year_to}, max={max_results}")

    st.divider()
    st.caption("支持的数据源: OpenAlex, Crossref, PubMed, arXiv, Semantic Scholar（通过 Unpaywall 确定 OA 状态）")

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
