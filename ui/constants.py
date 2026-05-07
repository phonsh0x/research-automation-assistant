"""
UI constants for Streamlit frontend.

All page lists, option menus, templates, and display labels live here
so that app.py and page modules can import them without duplication.
"""

# ============================================================================
# App metadata
# ============================================================================

VERSION = "0.2.0"
VERSION_LABEL = f"版本: {VERSION} (Phase 2)"
TECH_STACK_LABEL = "基于 DeepSeek-V4-Pro"

# ============================================================================
# Page navigation
# ============================================================================

PAGE_OPTIONS = [
    "首页 — 系统概览",
    "文献检索",
    "我的文献库",
    "全文获取 / PDF 下载",
    "PDF 转换",
    "RAG 智能问答",
    "课题组画像",
    "写作辅助",
    "系统设置",
]

PAGE_ICONS = {
    "首页 — 系统概览": ":house:",
    "文献检索": ":mag:",
    "我的文献库": ":books:",
    "全文获取 / PDF 下载": ":arrow_down:",
    "PDF 转换": ":page_facing_up:",
    "RAG 智能问答": ":brain:",
    "课题组画像": ":bar_chart:",
    "写作辅助": ":pencil:",
    "系统设置": ":gear:",
}

# ============================================================================
# Literature search
# ============================================================================

SEARCH_SOURCES = ["openalex", "crossref", "pubmed", "europe_pmc"]

SORT_OPTIONS = ["relevance", "year", "citations"]

SORT_LABELS = {
    "relevance": "相关度",
    "year": "年份",
    "citations": "引用数",
}

SEARCH_MODE_OPTIONS = ["backfill", "daily_watch"]

SEARCH_MODE_LABELS = {
    "backfill": "批量回填 (优先 OpenAlex)",
    "daily_watch": "日常监控 (优先 Crossref/PubMed)",
}

SEARCH_PAGE_MODES = ["按关键词检索", "重点期刊监控"]

# Top-tier journals for NSC boost feature
NSC_JOURNALS = ["Nature", "Science", "Cell", "PNAS"]

# ============================================================================
# Medicinal chemistry keyword templates
# ============================================================================

KEYWORD_TEMPLATES = {
    "靶向蛋白降解 (PROTAC/分子胶)": (
        'PROTAC OR "molecular glue" OR "targeted protein degradation"'
    ),
    "共价抑制剂": (
        '"covalent inhibitor" OR "irreversible inhibitor"'
        ' OR "targeted covalent inhibitor"'
    ),
    "变构调节剂": (
        '"allosteric modulator" OR "allosteric inhibitor"'
        ' OR "allosteric regulation"'
    ),
    "AI 驱动的药物发现": (
        '"AI-driven drug discovery" OR "machine learning drug design"'
        ' OR "deep learning drug discovery"'
    ),
    "基于片段的药物设计 FBDD": (
        '"fragment-based drug design" OR FBDD OR "fragment screening"'
    ),
    "抗肿瘤药物": (
        'anticancer OR antitumor OR "cancer drug discovery"'
    ),
    "天然产物药物化学": (
        '"natural product" AND "drug discovery"'
        ' OR "natural product chemistry"'
    ),
    "先导化合物优化": (
        '"lead optimization" OR "lead compound"'
        ' AND "medicinal chemistry"'
    ),
}

# ============================================================================
# Library
# ============================================================================

LIBRARY_SOURCE_FILTERS = ["全部", "openalex", "crossref", "pubmed", "europe_pmc"]

LIBRARY_DISPLAY_COUNTS = [10, 20, 50, 100]

EXPORT_FORMATS = ["BibTeX", "CSV", "JSON"]

# ============================================================================
# Fulltext acquisition
# ============================================================================

FULLTEXT_DISPLAY_COUNTS = [10, 20, 50, 100]

FULLTEXT_DOWNLOAD_STATUSES = [
    "pending",
    "attempted",
    "downloaded",
    "failed",
    "manual_review",
]

LEGAL_STATUS_OPTIONS = [
    "合法 OA",
    "合法订阅",
    "用户负责",
    "需人工确认",
    "禁止",
]

# ============================================================================
# Journal watch
# ============================================================================

WATCH_DAY_OPTIONS = [1, 3, 7, 14, 30]
