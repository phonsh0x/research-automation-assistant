"""Search-related service functions.

Encapsulates PaperSearcher, search_runs recovery, and journal-watch
orchestration.  Page callbacks call these, then write results into
session_state.
"""

import streamlit as st

from src.utils.logger import get_logger
from ui.services.repository_service import get_repository, clear_cached_stats

_log = get_logger("ui.search_ui_service")


# ============================================================================
# Keyword search
# ============================================================================

def _build_keyword_query(params: dict):
    """Build a SearchQuery from the flat params dict."""
    from src.paper_search.models import SearchQuery

    keywords = params.get("keywords", "")
    nsc_boost = params.get("nsc_boost", False)
    year_from = params.get("year_from")
    year_to = params.get("year_to")

    final_keywords = keywords
    if nsc_boost:
        final_keywords = f"({keywords}) AND (Nature OR Science OR Cell OR PNAS)"

    return SearchQuery(
        keywords=final_keywords,
        max_results=params.get("max_results", 20),
        year_from=year_from if year_from and year_from > 1900 else None,
        year_to=year_to if year_to and year_to < 2030 else None,
        sources=params.get("sources", ["openalex"]),
        sort_by=params.get("sort_by", "relevance"),
        filter_oa_only=params.get("oa_only", False),
    )


def execute_keyword_search(params: dict) -> dict:
    """Run a keyword search via PaperSearcher.

    Returns::

        {"success": bool, "data": {"papers": [...], "total_count": int,
         "errors": [...], "last_query": {...}}, "message": str, "error": str|None}
    """
    from src.paper_search.searcher import PaperSearcher

    try:
        query = _build_keyword_query(params)
        searcher = PaperSearcher()
        result = searcher.search(query)

        papers = [
            {
                "title": p.title,
                "authors": ", ".join(p.authors),
                "doi": p.doi or "",
                "year": p.year,
                "journal": p.journal or "",
                "abstract": (p.abstract or "")[:300],
                "oa_status": p.oa_status,
                "citation_count": p.citation_count,
                "source": p.source_api,
            }
            for p in result.papers
        ]

        last_query = {
            "keywords": query.keywords,
            "sources": params.get("sources", []),
            "year_from": params.get("year_from"),
            "year_to": params.get("year_to"),
            "max_results": params.get("max_results", 20),
        }

        clear_cached_stats()
        return {
            "success": True,
            "data": {
                "papers": papers,
                "total_count": result.total_count,
                "errors": result.errors,
                "last_query": last_query,
            },
            "message": f"检索完成，找到 {result.total_count} 篇论文",
            "error": None,
        }
    except Exception as exc:
        _log.error("Keyword search failed: %s", exc)
        return {
            "success": False,
            "data": {"papers": [], "total_count": 0, "errors": [str(exc)], "last_query": None},
            "message": "",
            "error": str(exc),
        }


# ============================================================================
# Restore last search
# ============================================================================

def restore_last_search() -> dict:
    """Read the most recent *search_runs* record and return matching papers.

    Returns::

        {"success": bool, "data": {"papers": [...], "run": {...}|None},
         "message": str, "error": str|None}
    """
    try:
        repo = get_repository()
        conn = repo.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT run_id, run_type, sources_used, query_keywords, total_found, "
                "new_added, updated_count, started_at "
                "FROM search_runs ORDER BY run_id DESC LIMIT 1"
            )
            row = cursor.fetchone()
        finally:
            conn.close()

        if row:
            run_dict = dict(row)
            papers_result = repo.search_papers(keyword="", limit=50)
            papers = papers_result if papers_result else []
            return {
                "success": True,
                "data": {"papers": papers, "run": run_dict},
                "message": f"最近检索: {run_dict['query_keywords']} ({run_dict['started_at']})",
                "error": None,
            }

        return {
            "success": True,
            "data": {"papers": [], "run": None},
            "message": "没有历史检索记录。",
            "error": None,
        }
    except Exception as exc:
        _log.error("restore_last_search failed: %s", exc)
        return {
            "success": False,
            "data": {"papers": [], "run": None},
            "message": "",
            "error": str(exc),
        }


# ============================================================================
# Journal watch
# ============================================================================

def execute_journal_watch(days: int, active_only: bool = True) -> dict:
    """Orchestrate RSS + API journal monitoring.

    Returns::

        {"success": bool, "data": {"deduped": int, "new_count": int},
         "message": str, "error": str|None}
    """
    from src.paper_search.journal_watchlist import JournalWatchlist
    from src.paper_search.rss_watcher import run_rss_watch
    from src.paper_search.aggregator import SearchAggregator
    from src.paper_search.openalex import OpenAlexSearcher

    try:
        wl = JournalWatchlist()
        journals = wl.get_journals(active_only=active_only)
        rss_urls = [j["rss_url"] for j in journals if j.get("rss_url")]
        journal_names = [j["name"] for j in journals if j.get("rss_url")]

        all_papers = []
        errors = []

        # RSS
        if rss_urls:
            try:
                rss_papers = run_rss_watch(rss_urls, journal_names, days=days)
                all_papers.extend(rss_papers)
            except Exception as e:
                errors.append(f"RSS 抓取异常: {e}")

        # API search for journals without RSS
        search_journals = [j["name"] for j in journals if not j.get("rss_url")]
        if search_journals:
            searcher = OpenAlexSearcher()
            for jname in search_journals[:5]:
                try:
                    papers = searcher.get_recent(jname, days=days)
                    all_papers.extend(papers)
                except Exception as e:
                    errors.append(f"检索 {jname} 失败: {e}")

        if all_papers:
            agg = SearchAggregator(searchers=[], repository=get_repository())
            deduped = agg.deduplicate(all_papers)
            save_stats = agg.save_results(deduped)
            agg.record_search_run(
                run_type="daily_watch",
                sources=["rss", "openalex"],
                keywords=f"期刊监控 ({days}天)",
                total_found=len(deduped),
                new_added=save_stats["new_count"],
            )
            clear_cached_stats()
            return {
                "success": True,
                "data": {
                    "deduped": len(deduped),
                    "new_count": save_stats["new_count"],
                    "total_before_dedup": len(all_papers),
                    "errors": errors,
                },
                "message": f"监控完成，共 {len(deduped)} 篇（新增 {save_stats['new_count']} 篇）",
                "error": None,
            }

        return {
            "success": True,
            "data": {"deduped": 0, "new_count": 0, "errors": errors},
            "message": "未发现新论文。",
            "error": None,
        }
    except Exception as exc:
        _log.error("execute_journal_watch failed: %s", exc)
        return {
            "success": False,
            "data": {"deduped": 0, "new_count": 0, "errors": []},
            "message": "",
            "error": str(exc),
        }
