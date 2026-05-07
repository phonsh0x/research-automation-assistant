"""Page modules — each exports a ``render()`` function."""

from ui.pages.dashboard import render as _dashboard
from ui.pages.literature_search import render as _literature_search
from ui.pages.library import render as _library
from ui.pages.fulltext_download import render as _fulltext_download
from ui.pages.pdf_convert import render as _pdf_convert
from ui.pages.rag_chat import render as _rag_chat
from ui.pages.group_profile import render as _group_profile
from ui.pages.writing_assistant import render as _writing_assistant
from ui.pages.settings import render as _settings

PAGE_RENDERERS = {
    "首页 — 系统概览": _dashboard,
    "文献检索": _literature_search,
    "我的文献库": _library,
    "全文获取 / PDF 下载": _fulltext_download,
    "PDF 转换": _pdf_convert,
    "RAG 智能问答": _rag_chat,
    "课题组画像": _group_profile,
    "写作辅助": _writing_assistant,
    "系统设置": _settings,
}
