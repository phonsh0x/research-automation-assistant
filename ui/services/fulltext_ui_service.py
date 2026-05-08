"""Fulltext-acquisition service functions.

Encapsulates FullTextAcquisitionService, ManualUploadResolver, and the
associated PaperRepository writes (pdf_status, fulltext_access audit).
"""

import tempfile
from pathlib import Path

from src.utils.logger import get_logger
from ui.services.repository_service import get_repository, clear_cached_stats

_log = get_logger("ui.fulltext_ui_service")

# ============================================================================
# Source-name display mapping
# ============================================================================

_SOURCE_LABELS: dict[str, str] = {
    "all_sources": "全部合法来源均未找到",
    "unpaywall": "Unpaywall",
    "pmc": "PubMed Central",
    "arxiv": "arXiv",
    "publisher_oa": "出版社开放获取",
    "institution_access": "校园网/机构授权访问",
    "manual_upload": "手动上传",
    "unknown": "未知来源",
}


def friendly_source(source: str) -> str:
    """Convert internal source name to a user-friendly label."""
    return _SOURCE_LABELS.get(source, source)


# ============================================================================
# FullTextAcquisitionService helpers
# ============================================================================

def _get_ft_service():
    """Create a FullTextAcquisitionService bound to the cached repo."""
    from src.fulltext.service import FullTextAcquisitionService
    return FullTextAcquisitionService(get_repository())


# ============================================================================
# Resolve / download / batch
# ============================================================================

def resolve_fulltext(paper_id: int) -> dict:
    """Query all legal sources for a paper's full text availability."""
    try:
        service = _get_ft_service()
        result = service.resolve(paper_id)
        return {
            "success": True,
            "data": result.to_dict(),
            "message": "",
            "error": None,
        }
    except Exception as exc:
        _log.error("resolve_fulltext(%d) failed: %s", paper_id, exc)
        return {"success": False, "data": None, "message": "", "error": str(exc)}


def download_fulltext(paper_id: int, user_confirmed_institution: bool = False) -> dict:
    """Download a single paper's PDF through legal channels."""
    try:
        service = _get_ft_service()
        result = service.download(paper_id, user_confirmed_institution=user_confirmed_institution)
        clear_cached_stats()
        return {
            "success": result.pdf_path is not None,
            "data": result.to_dict(),
            "message": "",
            "error": result.error_message if not result.pdf_path else None,
        }
    except Exception as exc:
        _log.error("download_fulltext(%d) failed: %s", paper_id, exc)
        return {"success": False, "data": None, "message": "", "error": str(exc)}


def batch_download_pending(paper_ids: list[int], user_confirmed_institution: bool = False) -> dict:
    """Download multiple papers' PDFs.  Returns per-paper results AND summary counts."""
    try:
        service = _get_ft_service()
        results = service.batch_download(paper_ids, user_confirmed_institution=user_confirmed_institution)
        data = [r.to_dict() for r in results]

        # Compute summary counts from result statuses
        downloaded = 0
        unavailable = 0
        manual_review = 0
        failed = 0
        skipped = 0

        for r in results:
            if r.pdf_path:
                downloaded += 1
            elif r.access_status == "unavailable":
                unavailable += 1
            elif r.access_status == "manual_review":
                manual_review += 1
            elif r.access_status in ("failed", "unsupported_source"):
                failed += 1
            else:
                skipped += 1

        # Map source names to friendly labels
        for item in data:
            raw = item.get("source", "")
            item["source_label"] = friendly_source(raw)

        clear_cached_stats()
        return {
            "success": True,
            "data": data,
            "summary": {
                "total": len(results),
                "downloaded": downloaded,
                "unavailable": unavailable,
                "manual_review": manual_review,
                "failed": failed,
                "skipped": skipped,
            },
            "message": "",
            "error": None,
        }
    except Exception as exc:
        _log.error("batch_download_pending failed: %s", exc)
        return {"success": False, "data": [], "summary": {}, "message": "", "error": str(exc)}


# ============================================================================
# Mark manual review
# ============================================================================

def mark_manual_review(paper_id: int, reason: str = "") -> dict:
    """Mark a paper as needing manual review."""
    try:
        repo = get_repository()
        ok = repo.mark_manual_review(paper_id, reason or "用户在 UI 中标记为需人工审查")
        if ok:
            clear_cached_stats()
            return {"success": True, "data": {"paper_id": paper_id}, "message": "", "error": None}
        return {"success": False, "data": None, "message": "", "error": "更新失败"}
    except Exception as exc:
        _log.error("mark_manual_review(%d) failed: %s", paper_id, exc)
        return {"success": False, "data": None, "message": "", "error": str(exc)}


# ============================================================================
# Manual upload
# ============================================================================

def handle_manual_upload(paper_id: int, uploaded_file, user_confirmed_rights: bool = True) -> dict:
    """Accept a user-provided PDF, validate, store, and update the database."""
    try:
        from src.fulltext.manual_upload import ManualUploadResolver

        repo = get_repository()
        paper = repo.get_paper_by_id(paper_id)
        if not paper:
            return {
                "success": False,
                "data": None,
                "message": f"论文 ID {paper_id} 不存在",
                "error": None,
            }

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name

        try:
            resolver = ManualUploadResolver()
            result = resolver.upload(paper, tmp_path, user_confirmed_rights=user_confirmed_rights)

            if result.pdf_path:
                repo.update_paper_pdf_status(
                    paper_id=paper_id,
                    pdf_path=result.pdf_path,
                    download_status="downloaded",
                    access_source="manual_upload",
                    legal_status=result.legal_status,
                )
                repo.record_fulltext_access(
                    paper_id=paper_id,
                    doi=paper.get("doi", ""),
                    title=paper.get("title", ""),
                    access_status="manual_upload",
                    access_source="manual_upload",
                    access_mode="manual",
                    legal_status=result.legal_status,
                    pdf_path=result.pdf_path,
                    file_size=result.file_size,
                    checksum_sha256=result.checksum_sha256,
                    risk_level=result.risk_level,
                    risk_note=result.risk_note,
                )
                clear_cached_stats()
                return {
                    "success": True,
                    "data": {
                        "pdf_path": result.pdf_path,
                        "file_size": result.file_size,
                        "filename": Path(result.pdf_path).name,
                    },
                    "message": f"PDF 已上传成功: {Path(result.pdf_path).name} ({result.file_size} 字节)",
                    "error": None,
                }

            return {
                "success": False,
                "data": None,
                "message": "",
                "error": result.error_message or "上传失败",
            }
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    except Exception as exc:
        _log.error("handle_manual_upload(%d) failed: %s", paper_id, exc)
        return {"success": False, "data": None, "message": "", "error": str(exc)}
