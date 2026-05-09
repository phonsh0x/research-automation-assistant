"""PDF upload ingest pipeline — runs as a background job handler.

The handler receives a job dict whose *payload_json* contains a list of
staged file dicts::

    {"files": [{"path": "/tmp/staged/paper.pdf", "name": "paper.pdf"}, ...]}

Files are first saved to disk by the UI thread, then the job processes
them in a background thread.  Streamlit UploadedFile objects never enter
the background payload.
"""

import hashlib
import json
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

from src.fulltext.pdf_metadata import extract_metadata
from src.files.path_resolver import ensure_directory, to_portable_path
from src.storage.repository import PaperRepository
from src.tasks.repository import JobRepository
from src.utils.logger import get_logger

_log = get_logger(__name__)


def _compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _process_one(staged_path: Path, original_name: str, db_path: str = "") -> dict:
    """Process a single staged file.  Returns {status, filename, doi, title, message}."""
    if db_path:
        from src.database.connection import DatabaseManager
        db = DatabaseManager(db_path)
        repo = PaperRepository(db=db)
        job_repo = JobRepository(db=db)
    else:
        repo = PaperRepository()
        job_repo = JobRepository()

    # Checksum
    checksum = _compute_sha256(staged_path)
    file_size = staged_path.stat().st_size

    # Duplicate
    existing = job_repo.get_upload_by_checksum(checksum)
    if existing:
        return {"status": "duplicate", "filename": original_name, "doi": "",
                "title": "", "message": "文件已存在（SHA256 重复）"}

    # Move to data/pdf (resolved against project root)
    inbox = ensure_directory("data/pdf")
    dest = inbox / original_name
    if dest.exists():
        stem, suffix = dest.stem, dest.suffix
        dest = inbox / f"{stem}_{datetime.now().strftime('%Y%m%d%H%M%S')}{suffix}"
    import shutil
    shutil.move(str(staged_path), str(dest))

    # Metadata
    meta = extract_metadata(dest)
    doi = meta.get("doi", "")
    title = meta.get("title", "")
    year = meta.get("year")
    authors = meta.get("authors", "")

    # Insert upload record
    upload_id = job_repo.insert_upload(
        filename=original_name, stored_path=to_portable_path(dest), file_size=file_size,
        checksum=checksum, doi=doi, title=title, year=year, authors=authors,
    )

    # Match
    matched_paper = None
    match_method = ""
    match_score = 0.0

    if doi:
        matched_paper = repo.get_paper_by_doi(doi)
        if matched_paper:
            match_method = "doi"
            match_score = 1.0

    if not matched_paper and title:
        candidates = repo.search_papers(keyword=title[:100], limit=10)
        best_score = 0.0
        best_paper = None
        for c in candidates:
            s = _similarity(title, c.get("title", ""))
            if s > best_score:
                best_score = s
                best_paper = c
        if best_score > 0.85:
            matched_paper = best_paper
            match_method = "title_similarity"
            match_score = best_score

    paper_id = None

    if matched_paper:
        paper_id = matched_paper.get("paper_id") or matched_paper.get("id")
        repo.update_paper_pdf_status(
            paper_id=paper_id, pdf_path=to_portable_path(dest),
            download_status="downloaded", access_source="manual_upload",
            legal_status="user_provided",
        )
        repo.record_fulltext_access(
            paper_id=paper_id, doi=doi or matched_paper.get("doi", ""),
            title=title or matched_paper.get("title", ""),
            access_status="manual_upload", access_source="manual_upload",
            access_mode="manual", legal_status="user_provided",
            pdf_path=to_portable_path(dest), file_size=file_size, checksum_sha256=checksum,
        )
        job_repo.update_upload(upload_id, status="merged", matched_paper_id=paper_id,
                               match_method=match_method, match_score=match_score)
        msg = f"已合并到已有论文（{match_method}）"
        status = "merged"
    else:
        from src.paper_search.models import PaperMetadata
        new_paper = PaperMetadata(
            title=title or original_name, doi=doi or None, year=year,
            source_api="manual_upload",
        )
        paper_id, _ = repo.upsert_paper(new_paper)
        repo.update_paper_pdf_status(
            paper_id=paper_id, pdf_path=to_portable_path(dest),
            download_status="downloaded", access_source="manual_upload",
            legal_status="user_provided",
        )
        repo.record_fulltext_access(
            paper_id=paper_id, doi=doi, title=title,
            access_status="manual_upload", access_source="manual_upload",
            access_mode="manual", legal_status="user_provided",
            pdf_path=to_portable_path(dest), file_size=file_size, checksum_sha256=checksum,
        )
        job_repo.update_upload(upload_id, status="created", matched_paper_id=paper_id,
                               match_method="new", match_score=0.0)
        msg = "已新建论文记录"
        status = "created"

    return {"status": status, "filename": original_name, "doi": doi or "—",
            "title": title or original_name, "message": msg}


def handle_upload_job(job: dict):
    """Background job handler for pdf_upload_ingest.

    Expects ``job["payload_json"]`` to be a JSON string containing
    ``{"files": [{"path": "...", "name": "..."}, ...]}``.

    When ``_db_path`` is present in the job dict, the handler and all
    sub-routines use that database instead of the default data/paper.db.
    """
    db_path = job.get("_db_path", "")
    if db_path:
        from src.database.connection import DatabaseManager
        job_repo = JobRepository(db=DatabaseManager(db_path))
    else:
        job_repo = JobRepository()
    job_id = job["job_id"]

    try:
        payload = json.loads(job.get("payload_json", "{}"))
    except (json.JSONDecodeError, TypeError):
        job_repo.update_job(job_id, status="failed", error_message="Invalid payload",
                            finished_at=datetime.now().isoformat())
        return

    files = payload.get("files", [])
    if not files:
        job_repo.update_job(job_id, status="failed", error_message="No files in payload",
                            finished_at=datetime.now().isoformat())
        return

    total = len(files)
    job_repo.update_job(job_id, progress_total=total, message=f"处理中 0/{total}")

    results = []
    merged = created = dup = failed = 0

    for i, f in enumerate(files):
        path = Path(f["path"])
        name = f.get("name", path.name)
        if not path.exists():
            r = {"status": "failed", "filename": name, "doi": "", "title": "",
                 "message": "文件不存在"}
            failed += 1
        else:
            r = _process_one(path, name, db_path=db_path)
            if r["status"] == "merged":
                merged += 1
            elif r["status"] == "created":
                created += 1
            elif r["status"] == "duplicate":
                dup += 1
            else:
                failed += 1
        results.append(r)
        job_repo.update_job(job_id, progress_current=i + 1,
                            message=f"处理中 {i + 1}/{total}")

    summary = f"上传完成: 合并 {merged}, 新建 {created}, 重复 {dup}, 失败 {failed}"
    job_repo.update_job(
        job_id, status="success",
        result_json=json.dumps({"results": results, "merged": merged,
                                "created": created, "duplicate": dup, "failed": failed},
                               ensure_ascii=False),
        message=summary, finished_at=datetime.now().isoformat(),
    )
