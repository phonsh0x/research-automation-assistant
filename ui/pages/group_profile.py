"""Group profile page — placeholder (Phase 3)."""

import streamlit as st

from ui.components.layout import render_page_header
from ui.components.messages import render_page_message


def render():
    render_page_header("课题组画像", "分析课题组已发表论文，生成研究方向画像。")
    render_page_message()
    st.info("课题组画像功能将在 Phase 3 中实现。")
    st.markdown("""
    #### 即将支持的功能
    - 研究方向自动抽取
    - 关键词云和主题演化趋势
    - 合作者网络可视化
    - Markdown 分析报告
    """)
