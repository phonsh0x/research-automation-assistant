"""PDF-to-Markdown conversion UI service."""

from pathlib import Path

from src.utils.logger import get_logger
from ui.services.repository_service import get_repository, clear_cached_stats

_log = get_logger("ui.pdf_convert_ui_service")

# Project root for resolving relative pdf/md paths
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _resolve_path(raw: str | None) -> Path | None:
    """Resolve a possibly-relative path against the project root."""
    if not raw:
        return None
    p = Path(raw)
    if p.is_absolute():
        return p if p.exists() else None
    resolved = _PROJECT_ROOT / p
    return resolved if resolved.exists() else None


def _pdf_status(raw_path: str | None) -> tuple[bool, str]:
    """Return (available, label) for a pdf_path."""
    if not raw_path:
        return False, "路径缺失"
    resolved = _resolve_path(raw_path)
    if resolved is None:
        return False, "文件不存在"
    if resolved.suffix.lower() != ".pdf":
        return False, "格式异常"
    return True, "已存在"


def _md_status(raw_path: str | None) -> tuple[bool, str]:
    """Return (available, label) for an md_path."""
    if not raw_path:
        return False, "未转换"
    if _resolve_path(raw_path) is None:
        return False, "未转换"
    return True, "已转换"


def get_conversion_stats() -> dict:
    """Return conversion statistics."""
    try:
        repo = get_repository()
        return {"success": True, "data": repo.get_conversion_statistics(), "message": "", "error": None}
    except Exception as exc:
        _log.error("get_conversion_stats failed: %s", exc)
        return {"success": False, "data": {}, "message": "", "error": str(exc)}


def get_pending_papers(limit: int = 20) -> dict:
    """Return papers with PDF but no Markdown, with normalised fields and stable sort."""
    try:
        repo = get_repository()
        raw = repo.get_papers_with_pdf_without_markdown(limit=limit)
        papers = []
        for p in raw:
            pdf_path = p.get("pdf_path")
            pdf_avail, pdf_label = _pdf_status(pdf_path)
            md_path = p.get("md_path")
            md_avail, md_label = _md_status(md_path)

            papers.append({
                "paper_id": p.get("paper_id"),
                "title": p.get("title") or "未命名论文",
                "authors": p.get("authors") or "未知",
                "year": p.get("year"),
                "journal": p.get("journal"),
                "doi": p.get("doi"),
                "pdf_path": pdf_path,
                "pdf_available": pdf_avail,
                "pdf_status_label": pdf_label,
                "md_path": md_path,
                "md_available": md_avail,
                "md_status_label": md_label,
            })

        papers.sort(key=lambda x: (
            -(x.get("year") or 0),
            x.get("title", ""),
            x.get("paper_id", 0),
        ))

        return {"success": True, "data": {"papers": papers, "count": len(papers)}, "message": "", "error": None}
    except Exception as exc:
        _log.error("get_pending_papers failed: %s", exc)
        return {"success": False, "data": {"papers": [], "count": 0}, "message": "", "error": str(exc)}


def convert_single(paper_id: int) -> dict:
    """Convert a single paper's PDF to Markdown."""
    from src.pdf_converter import PDFConverter

    try:
        repo = get_repository()
        paper = repo.get_paper_by_id(paper_id)
        if not paper:
            return {"success": False, "data": None, "message": "该论文不存在", "error": None}

        pdf_path = paper.get("pdf_path", "")
        resolved = _resolve_path(pdf_path)
        if resolved is None:
            return {"success": False, "data": None, "message": "",
                    "error": "当前论文没有可用的 PDF 文件，请先在全文获取页面下载或手动上传 PDF。"}

        converter = PDFConverter()
        result = converter.convert(resolved)
        result.paper_id = paper_id

        if result.status == "success":
            repo.update_paper_markdown_status(paper_id, result.md_path)
            repo.record_full_text(result)
            clear_cached_stats()

        return {"success": result.status == "success", "data": result.to_dict(), "message": "",
                "error": result.error_message}
    except Exception as exc:
        _log.error("convert_single(%d) failed: %s", paper_id, exc)
        return {"success": False, "data": None, "message": "", "error": str(exc)}


def convert_batch(limit: int = 10) -> dict:
    """Convert all pending papers."""
    try:
        repo = get_repository()
        papers = repo.get_papers_with_pdf_without_markdown(limit=limit)
        if not papers:
            return {"success": True, "data": {"results": [], "total": 0, "success_count": 0},
                    "message": "没有待转换的论文", "error": None}

        from src.pdf_converter import PDFConverter
        converter = PDFConverter()
        results_data = []
        ok = 0

        for p in papers:
            pid = p.get("paper_id")
            pdf_path = p.get("pdf_path", "")
            resolved = _resolve_path(pdf_path)
            if resolved is None:
                results_data.append({"paper_id": pid, "status": "skipped", "error_message": "缺少可用 PDF 文件"})
                continue

            result = converter.convert(resolved)
            result.paper_id = pid
            d = result.to_dict()

            if result.status == "success":
                repo.update_paper_markdown_status(pid, result.md_path)
                repo.record_full_text(result)
                ok += 1

            results_data.append(d)

        clear_cached_stats()
        return {
            "success": True,
            "data": {"results": results_data, "total": len(papers), "success_count": ok},
            "message": f"批量转换完成: {ok}/{len(papers)} 成功",
            "error": None,
        }
    except Exception as exc:
        _log.error("convert_batch failed: %s", exc)
        return {"success": False, "data": {"results": [], "total": 0, "success_count": 0}, "message": "", "error": str(exc)}


def get_markdown_preview(paper_id: int) -> dict:
    """Return the Markdown content for a converted paper."""
    try:
        repo = get_repository()
        paper = repo.get_paper_by_id(paper_id)
        if not paper:
            return {"success": False, "data": None, "message": "该论文不存在", "error": None}

        md_path = paper.get("md_path", "")
        resolved = _resolve_path(md_path)
        if resolved is None:
            return {"success": False, "data": None, "message": "", "error": "Markdown 文件不存在，请先转换"}

        content = resolved.read_text(encoding="utf-8")
        return {"success": True, "data": content[:50000], "message": "", "error": None}
    except Exception as exc:
        _log.error("get_markdown_preview(%d) failed: %s", paper_id, exc)
        return {"success": False, "data": None, "message": "", "error": str(exc)}


def convert_selected(paper_ids: list[int]) -> dict:
    """Convert a specific list of paper IDs in batch."""
    if not paper_ids:
        return {"success": True,
                "data": {"results": [], "total": 0, "success_count": 0, "failed_count": 0, "skipped_count": 0},
                "message": "没有选中任何论文", "error": None}

    try:
        repo = get_repository()
        from src.pdf_converter import PDFConverter
        converter = PDFConverter()
        results_data = []
        ok = 0
        failed = 0
        skipped = 0

        for pid in paper_ids:
            paper = repo.get_paper_by_id(pid)
            if not paper:
                results_data.append({"paper_id": pid, "status": "skipped", "error_message": "论文不存在"})
                skipped += 1
                continue

            pdf_path = paper.get("pdf_path", "")
            resolved = _resolve_path(pdf_path)
            if resolved is None:
                results_data.append({"paper_id": pid, "status": "skipped", "error_message": "缺少可用 PDF 文件"})
                skipped += 1
                continue

            result = converter.convert(resolved)
            result.paper_id = pid
            d = result.to_dict()

            if result.status == "success":
                repo.update_paper_markdown_status(pid, result.md_path)
                repo.record_full_text(result)
                ok += 1
            elif result.status == "failed":
                failed += 1
            else:
                skipped += 1

            results_data.append(d)

        clear_cached_stats()
        return {
            "success": True,
            "data": {
                "results": results_data,
                "total": len(paper_ids),
                "success_count": ok,
                "failed_count": failed,
                "skipped_count": skipped,
            },
            "message": f"批量转换完成: 成功 {ok}, 失败 {failed}, 跳过 {skipped}",
            "error": None,
        }
    except Exception as exc:
        _log.error("convert_selected failed: %s", exc)
        return {"success": False,
                "data": {"results": [], "total": 0, "success_count": 0, "failed_count": 0, "skipped_count": 0},
                "message": "", "error": str(exc)}
