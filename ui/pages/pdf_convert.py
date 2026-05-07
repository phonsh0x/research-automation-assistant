"""PDF-to-Markdown conversion page — placeholder (Phase 2.3)."""

import streamlit as st

from ui.state import ui_key
from ui.components.layout import render_page_header
from ui.components.messages import render_page_message


def render():
    render_page_header("PDF 转 Markdown", "将学术 PDF 论文转换为结构化 Markdown。")
    render_page_message()
    st.info("PDF 转换功能将在 Phase 2 中实现。转换引擎支持 marker, pymupdf, nougat。")

    uploaded_pdf = st.file_uploader("上传 PDF 文件", type=["pdf"], key=ui_key("pdf_convert", "upload_file"))
    if uploaded_pdf:
        st.info("PDF 上传成功，但转换功能尚未实现。")
