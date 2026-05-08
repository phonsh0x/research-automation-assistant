"""Writing assistant page — placeholder (Phase 3)."""

import streamlit as st

from ui.state import ui_key
from ui.components.layout import render_page_header
from ui.components.messages import render_page_message


def render():
    render_page_header("写作辅助", "中文学术写作助手，辅助撰写文献综述、基金申请书和学术论文。")
    render_page_message()
    st.info("写作辅助功能将在 Phase 3 中实现。")

    writing_type = st.selectbox(
        "写作类型",
        ["文献综述", "基金申请书-立项依据", "学术论文摘要", "方法描述", "文字润色"],
        key="writing_type",
    )

    text_input = st.text_area(
        "输入写作主题或待润色文本",
        placeholder="请输入写作主题或待润色的文本...",
        height=150,
        key="writing_input",
    )

    if st.button("生成/润色", key=ui_key("writing", "generate_btn"), type="primary"):
        if text_input:
            st.info(f"写作辅助请求已收到: '{writing_type}'。功能将在 Phase 3 实现。")
