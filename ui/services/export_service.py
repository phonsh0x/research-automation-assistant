"""Export service — BibTeX, CSV, JSON."""

import csv
import io
import json

from src.utils.logger import get_logger
from ui.services.repository_service import get_repository

_log = get_logger("ui.export_service")


def export_bibtex() -> dict:
    """Return BibTeX string for all papers in the repository."""
    try:
        repo = get_repository()
        bibtex = repo.export_bibtex()
        if bibtex:
            return {"success": True, "data": bibtex, "message": "", "error": None}
        return {
            "success": False,
            "data": None,
            "message": "没有可导出的论文。",
            "error": None,
        }
    except Exception as exc:
        _log.error("export_bibtex failed: %s", exc)
        return {"success": False, "data": None, "message": "", "error": str(exc)}


def export_csv() -> dict:
    """Return CSV string for all papers."""
    try:
        repo = get_repository()
        papers = repo.search_papers(keyword="", limit=10000)
        if not papers:
            return {
                "success": False,
                "data": None,
                "message": "没有可导出的论文。",
                "error": None,
            }

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["ID", "标题", "作者", "年份", "期刊", "DOI", "OA状态", "来源"])
        for p in papers:
            writer.writerow([
                p.get("id") or p.get("paper_id", ""),
                p.get("title", ""),
                p.get("authors", ""),
                p.get("year", ""),
                p.get("journal", ""),
                p.get("doi", ""),
                p.get("oa_status", ""),
                p.get("source", ""),
            ])
        return {"success": True, "data": buf.getvalue(), "message": "", "error": None}
    except Exception as exc:
        _log.error("export_csv failed: %s", exc)
        return {"success": False, "data": None, "message": "", "error": str(exc)}


def export_json() -> dict:
    """Return JSON string for all papers."""
    try:
        repo = get_repository()
        papers = repo.search_papers(keyword="", limit=10000)
        if not papers:
            return {
                "success": False,
                "data": None,
                "message": "没有可导出的论文。",
                "error": None,
            }
        return {"success": True, "data": json.dumps(papers, ensure_ascii=False, default=str), "message": "", "error": None}
    except Exception as exc:
        _log.error("export_json failed: %s", exc)
        return {"success": False, "data": None, "message": "", "error": str(exc)}
