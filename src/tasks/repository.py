"""Database CRUD for background_jobs and uploaded_files tables."""

from src.database.connection import DatabaseManager
from src.utils.logger import get_logger

_log = get_logger(__name__)


class JobRepository:
    def __init__(self, db: DatabaseManager | None = None):
        self.db = db or DatabaseManager()

    # ---- background_jobs ----

    def create_job(self, job_type: str, title: str = "", payload: dict | None = None) -> int:
        import json
        conn = self.db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO background_jobs (job_type, title, payload_json, status) VALUES (?, ?, ?, 'pending')",
                (job_type, title, json.dumps(payload, ensure_ascii=False) if payload else None),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get_job(self, job_id: int) -> dict | None:
        conn = self.db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM background_jobs WHERE job_id = ?", (job_id,))
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_jobs(self, status: str | None = None, job_type: str | None = None,
                  limit: int = 50) -> list[dict]:
        conn = self.db.get_connection()
        try:
            cur = conn.cursor()
            conditions = []
            params: list = []
            if status:
                conditions.append("status = ?")
                params.append(status)
            if job_type:
                conditions.append("job_type = ?")
                params.append(job_type)
            where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
            params.append(limit)
            cur.execute(
                f"SELECT * FROM background_jobs{where} ORDER BY job_id DESC LIMIT ?",
                params,
            )
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def update_job(self, job_id: int, **kwargs) -> bool:
        if not kwargs:
            return False
        setters = [f"{k} = ?" for k in kwargs]
        values = list(kwargs.values()) + [job_id]
        conn = self.db.get_connection()
        try:
            conn.execute(
                f"UPDATE background_jobs SET {', '.join(setters)} WHERE job_id = ?",
                values,
            )
            conn.commit()
            return True
        except Exception as exc:
            _log.error("update_job(%d) failed: %s", job_id, exc)
            return False
        finally:
            conn.close()

    # ---- job status helpers ----

    def get_running_jobs(self) -> list[dict]:
        """Return all jobs currently in 'running' status."""
        return self.list_jobs(status="running", limit=9999)

    def update_job_progress(self, job_id: int, current: int, total: int,
                            message: str = "") -> bool:
        return self.update_job(
            job_id, progress_current=current, progress_total=total, message=message,
        )

    def mark_job_running(self, job_id: int) -> bool:
        from datetime import datetime
        return self.update_job(
            job_id, status="running", started_at=datetime.now().isoformat(),
        )

    def mark_job_success(self, job_id: int, message: str = "",
                         result_json: str = "") -> bool:
        from datetime import datetime
        kwargs: dict = {"status": "success", "finished_at": datetime.now().isoformat()}
        if message:
            kwargs["message"] = message
        if result_json:
            kwargs["result_json"] = result_json
        return self.update_job(job_id, **kwargs)

    def mark_job_failed(self, job_id: int, error_message: str = "") -> bool:
        from datetime import datetime
        kwargs: dict = {"status": "failed", "finished_at": datetime.now().isoformat()}
        if error_message:
            kwargs["error_message"] = error_message
        return self.update_job(job_id, **kwargs)

    def mark_job_interrupted(self, job_id: int, message: str = "") -> bool:
        from datetime import datetime
        kwargs: dict = {"status": "interrupted",
                        "finished_at": datetime.now().isoformat()}
        if message:
            kwargs["error_message"] = message
        return self.update_job(job_id, **kwargs)

    def mark_stale_running_jobs_as_interrupted(self) -> int:
        """Mark all running jobs with no finished_at as interrupted.

        Returns the number of jobs that were cleaned up.
        """
        conn = self.db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """UPDATE background_jobs
                   SET status = 'interrupted',
                       error_message = '上次程序退出导致任务中断',
                       finished_at = CURRENT_TIMESTAMP
                   WHERE status = 'running' AND finished_at IS NULL""",
            )
            conn.commit()
            count = cur.rowcount
            if count > 0:
                _log.warning("Marked %d stale running job(s) as interrupted", count)
            return count
        except Exception as exc:
            _log.error("mark_stale_running_jobs_as_interrupted failed: %s", exc)
            return 0
        finally:
            conn.close()

    # ---- uploaded_files ----

    def insert_upload(self, filename: str, stored_path: str, file_size: int,
                      checksum: str, doi: str = "", title: str = "",
                      year: int | None = None, authors: str = "") -> int:
        conn = self.db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO uploaded_files
                   (original_filename, stored_path, file_size, checksum_sha256,
                    detected_doi, detected_title, detected_year, detected_authors, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'staged')""",
                (filename, stored_path, file_size, checksum, doi, title, year, authors),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def update_upload(self, upload_id: int, **kwargs) -> bool:
        if not kwargs:
            return False
        setters = [f"{k} = ?" for k in kwargs]
        values = list(kwargs.values()) + [upload_id]
        conn = self.db.get_connection()
        try:
            conn.execute(
                f"UPDATE uploaded_files SET {', '.join(setters)}, updated_at = CURRENT_TIMESTAMP WHERE upload_id = ?",
                values,
            )
            conn.commit()
            return True
        except Exception as exc:
            _log.error("update_upload(%d) failed: %s", upload_id, exc)
            return False
        finally:
            conn.close()

    def get_upload_by_checksum(self, checksum: str) -> dict | None:
        conn = self.db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM uploaded_files WHERE checksum_sha256 = ?", (checksum,))
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
