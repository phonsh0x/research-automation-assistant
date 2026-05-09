"""Cached access to PaperRepository and its statistics.

Every function that returns data uses the unified result dict:
    {"success": bool, "data": ..., "message": str, "error": str | None}
"""

import streamlit as st

from src.utils.logger import get_logger

_log = get_logger("ui.repository_service")


# ============================================================================
# Cached singletons
# ============================================================================

@st.cache_resource
def get_repository():
    """Cached PaperRepository singleton."""
    from src.storage.repository import PaperRepository
    return PaperRepository()


@st.cache_data(ttl=60)
def get_db_stats() -> dict:
    """Cached database-wide statistics (60 s TTL)."""
    try:
        repo = get_repository()
        data = repo.get_statistics()
        return {"success": True, "data": data, "message": "", "error": None}
    except Exception as exc:
        _log.error("Failed to get db stats: %s", exc)
        return {"success": False, "data": {}, "message": "", "error": str(exc)}


@st.cache_data(ttl=30)
def get_download_stats() -> dict:
    """Cached download statistics (30 s TTL)."""
    try:
        repo = get_repository()
        data = repo.get_download_statistics()
        return {"success": True, "data": data, "message": "", "error": None}
    except Exception as exc:
        _log.error("Failed to get download stats: %s", exc)
        return {"success": False, "data": {}, "message": "", "error": str(exc)}


def clear_cached_stats():
    """Invalidate the cached statistics (call after mutations)."""
    get_db_stats.clear()
    get_download_stats.clear()


# ============================================================================
# Repository queries
# ============================================================================

def search_library(
    keyword: str = "",
    limit: int = 20,
    offset: int = 0,
    source: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
) -> dict:
    """Search the local paper repository."""
    try:
        repo = get_repository()
        papers = repo.search_papers(
            keyword=keyword,
            limit=limit,
            offset=offset,
            source=source,
            year_from=year_from,
            year_to=year_to,
        )
        return {
            "success": True,
            "data": {"papers": papers, "count": len(papers)},
            "message": "",
            "error": None,
        }
    except Exception as exc:
        _log.error("Library search failed: %s", exc)
        return {"success": False, "data": {"papers": [], "count": 0}, "message": "", "error": str(exc)}


def get_pending_papers(limit: int = 20) -> dict:
    """Return papers that still need PDF download."""
    try:
        repo = get_repository()
        papers = repo.get_papers_without_pdf(limit=limit)
        return {
            "success": True,
            "data": {"papers": papers, "count": len(papers)},
            "message": "",
            "error": None,
        }
    except Exception as exc:
        _log.error("get_pending_papers failed: %s", exc)
        return {"success": False, "data": {"papers": [], "count": 0}, "message": "", "error": str(exc)}


def get_paper_detail(paper_id: int) -> dict:
    """Return a single paper's full metadata."""
    try:
        repo = get_repository()
        paper = repo.get_paper_by_id(paper_id)
        if paper is None:
            return {"success": False, "data": None, "message": "该论文不存在", "error": None}
        return {"success": True, "data": paper, "message": "", "error": None}
    except Exception as exc:
        _log.error("get_paper_detail(%d) failed: %s", paper_id, exc)
        return {"success": False, "data": None, "message": "", "error": str(exc)}
