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

    def list_jobs(self, status: str | None = None, limit: int = 50) -> list[dict]:
        conn = self.db.get_connection()
        try:
            cur = conn.cursor()
            if status:
                cur.execute(
                    "SELECT * FROM background_jobs WHERE status = ? ORDER BY job_id DESC LIMIT ?",
                    (status, limit),
                )
            else:
                cur.execute(
                    "SELECT * FROM background_jobs ORDER BY job_id DESC LIMIT ?",
                    (limit,),
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
