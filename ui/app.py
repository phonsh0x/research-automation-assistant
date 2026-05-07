"""
Streamlit 交互界面 — 科研自动化助手前端。

启动方式：
  streamlit run ui/app.py

页面导航（侧边栏）：
  - 首页 / 系统概览
  - 文献检索
  - 我的文献库
  - 全文获取 / PDF 下载
  - PDF 转换
  - RAG 智能问答
  - 课题组画像
  - 写作辅助
  - 系统设置

状态管理：
  所有关键页面状态通过 st.session_state 持久化，切换页面后不会丢失。
"""

import sys
from pathlib import Path

# 将项目根目录添加到 Python 路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from ui.state import ui_key, init_session_state, clear_search_state, clear_fulltext_state, set_page_message
from ui.constants import PAGE_OPTIONS, VERSION_LABEL, TECH_STACK_LABEL
from ui.styles import apply_page_config, apply_global_styles
from ui.pages import PAGE_RENDERERS

# ============================================================================
# 页面配置（必须是第一个 Streamlit 命令）
# ============================================================================
apply_page_config()
apply_global_styles()

init_session_state()


# ============================================================================
# 侧边栏导航
# ============================================================================

def render_sidebar():
    """Render the persistent sidebar and return the selected page key."""
    with st.sidebar:
        st.title(":books: 科研自动化助手")
        st.caption("课题组文献管理与科研辅助系统")
        st.divider()

        current = st.session_state.get("current_page", PAGE_OPTIONS[0])
        default_index = PAGE_OPTIONS.index(current) if current in PAGE_OPTIONS else 0

        page = st.radio(
            "导航",
            options=PAGE_OPTIONS,
            index=default_index,
            key="current_page",
        )

        st.divider()

        with st.expander("快速操作"):
            if st.button("清空检索结果", key=ui_key("sidebar", "clear_search"), use_container_width=True):
                clear_search_state()
                set_page_message("info", "检索结果已清空。")
                st.rerun()

            if st.button("清空全文获取状态", key=ui_key("sidebar", "clear_fulltext"), use_container_width=True):
                clear_fulltext_state()
                set_page_message("info", "全文获取状态已清空。")
                st.rerun()

        st.divider()
        st.caption(VERSION_LABEL)
        st.caption(TECH_STACK_LABEL)

    return page


# ============================================================================
# 主入口
# ============================================================================

def main():
    page = render_sidebar()

    render_func = PAGE_RENDERERS.get(page)
    if render_func:
        render_func()

    # 页脚
    st.sidebar.divider()
    st.sidebar.caption("2026 课题组科研自动化助手")


if __name__ == "__main__":
    main()
