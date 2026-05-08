"""RAG Q&A page — placeholder (Phase 2.5)."""

import streamlit as st

from ui.state import ui_key
from ui.components.layout import render_page_header
from ui.components.messages import render_page_message


def render():
    render_page_header("RAG 智能问答", "基于本地文献库的检索增强生成问答。")
    render_page_message()
    st.info("RAG 问答功能将在 Phase 2 中实现。回答将基于本地已入库文献生成。")

    question = st.text_area(
        "请输入您的问题",
        placeholder="例如: U-Net 架构在医学图像分割中有哪些改进变体？",
        key="rag_question",
    )
    col1, col2 = st.columns([1, 5])
    with col1:
        submit = st.button("提交问题", key=ui_key("rag", "submit_btn"), type="primary")

    if submit and question:
        st.info(f"问题已收到: '{question[:80]}...'。RAG 问答将在 Phase 2 实现。")
