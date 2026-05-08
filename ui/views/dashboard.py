"""Dashboard / home page — system overview and stats cards."""

import streamlit as st

from ui.components.layout import render_page_header
from ui.components.messages import render_page_message
from ui.components.metric_cards import render_database_stats
from ui.services.repository_service import get_db_stats, get_download_stats


def render():
    render_page_header("系统概览")

    render_page_message()

    st.markdown("""
    ### 欢迎使用课题组科研自动化助手

    本系统覆盖学术研究的全链路，帮助课题组高效管理文献和辅助科研写作。

    #### 当前阶段: Phase 2 — 智能功能

    | 功能模块 | 状态 | 说明 |
    |---------|------|------|
    | 文献检索 | 已完成 | 通过 OpenAlex/Crossref/PubMed/Europe PMC 检索文献 |
    | 全文获取 | 已完成 | 通过 Unpaywall/PMC/arXiv 等合法 API 获取 OA PDF |
    | 入库管理 | 已完成 | SQLite 数据库存储和管理文献元数据 |
    | PDF 转换 | Phase 2 | 学术 PDF 转结构化 Markdown |
    | RAG 问答 | Phase 2 | 基于本地文献库的智能问答 |
    | 课题组画像 | Phase 3 | 研究方向分析和合作网络 |
    | 写作辅助 | Phase 3 | 文献综述和基金申请书辅助 |
    """)

    db_stats_result = get_db_stats()
    ft_stats_result = get_download_stats()
    db_stats = db_stats_result.get("data", {})
    ft_stats = ft_stats_result.get("data", {})
    render_database_stats(db_stats, ft_stats)

    st.markdown("""
    #### 快速开始
    1. 在侧边栏选择"文献检索"，尝试检索论文
    2. 切换"全文获取 / PDF 下载"页面下载 PDF
    3. 在"系统设置"中配置 API Key 等参数
    4. 使用"RAG 智能问答"基于本地文献库提问

    #### 法律声明
    本系统仅通过合法开放 API 获取文献全文，严禁使用 Sci-Hub 或任何绕过付费墙的手段。
    """)
