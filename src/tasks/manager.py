"""Light-weight background TaskManager using ThreadPoolExecutor.

A module-level singleton ``_manager`` is initialised on first import with
the ``pdf_upload_ingest`` handler pre-registered.
"""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from src.tasks.repository import JobRepository
from src.utils.logger import get_logger

_log = get_logger(__name__)


class TaskManager:
    def __init__(self, max_workers: int = 3, repo=None, db_path=None):
        self.repo = repo or JobRepository()
        self._db_path = str(db_path) if db_path else None
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="bgjob")
        self._handlers: dict[str, callable] = {}

    def register_handler(self, job_type: str, handler: callable):
        self._handlers[job_type] = handler

    def submit(self, job_type: str, title: str = "", payload: dict | None = None) -> int:
        job_id = self.repo.create_job(job_type, title, payload)
        self._executor.submit(self._run, job_id, job_type)
        return job_id

    def _run(self, job_id: int, job_type: str):
        handler = self._handlers.get(job_type)
        if not handler:
            self.repo.update_job(job_id, status="failed", error_message=f"No handler for {job_type}")
            return

        self.repo.update_job(job_id, status="running", started_at=datetime.now().isoformat())
        job = self.repo.get_job(job_id)
        if self._db_path:
            job["_db_path"] = self._db_path
        try:
            handler(job)
        except Exception as exc:
            _log.error("Job %d (%s) failed: %s", job_id, job_type, exc)
            self.repo.update_job(
                job_id, status="failed", error_message=str(exc),
                finished_at=datetime.now().isoformat(),
            )

    def get_job(self, job_id: int) -> dict | None:
        return self.repo.get_job(job_id)

    def list_jobs(self, status: str | None = None, limit: int = 50) -> list[dict]:
        return self.repo.list_jobs(status, limit)

    def shutdown(self, wait: bool = False):
        self._executor.shutdown(wait=wait)


# ---------------------------------------------------------------------------
# Singleton initialisation
# ---------------------------------------------------------------------------

_manager: TaskManager | None = None


def _init_manager() -> TaskManager:
    global _manager
    if _manager is not None:
        return _manager
    _manager = TaskManager()
    from src.fulltext.upload_ingest import handle_upload_job
    _manager.register_handler("pdf_upload_ingest", handle_upload_job)
    _log.info("TaskManager singleton initialised")
    return _manager


def get_task_manager() -> TaskManager:
    return _init_manager()
