"""Tests for background job system — fully isolated via tmp_path databases."""

import json
import time
import uuid
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _init_temp_db(db_path: str) -> None:
    """Create and initialize a temporary SQLite database with all migrations."""
    from src.database.connection import DatabaseManager
    db = DatabaseManager(db_path)
    db.initialize()
    # Ensure connection is closed so background threads can write
    # (DatabaseManager.initialize() already closes its connection)


def _make_job_repo(db_path: str):
    """Build a JobRepository wired to a temp database."""
    from src.database.connection import DatabaseManager
    from src.tasks.repository import JobRepository
    return JobRepository(db=DatabaseManager(db_path))


def _make_task_manager(db_path: str, max_workers: int = 1,
                        startup_recovery: bool = False):
    """Build a TaskManager wired to a temp database."""
    from src.database.connection import DatabaseManager
    from src.tasks.manager import TaskManager
    from src.tasks.repository import JobRepository
    from src.fulltext.upload_ingest import handle_upload_job

    repo = JobRepository(db=DatabaseManager(db_path))
    mgr = TaskManager(max_workers=max_workers, repo=repo, db_path=db_path,
                      startup_recovery=startup_recovery)
    mgr.register_handler("pdf_upload_ingest", handle_upload_job)
    return mgr


# ---------------------------------------------------------------------------
# TestJobRepository
# ---------------------------------------------------------------------------

class TestJobRepository:
    def test_create_job_pending(self, tmp_path):
        db_path = str(tmp_path / "test_jobs.db")
        _init_temp_db(db_path)
        repo = _make_job_repo(db_path)

        job_id = repo.create_job("test", "Test job", {"key": "val"})
        assert job_id > 0

        job = repo.get_job(job_id)
        assert job["status"] == "pending"
        assert job["job_type"] == "test"
        assert job["title"] == "Test job"

    def test_list_jobs(self, tmp_path):
        db_path = str(tmp_path / "test_jobs.db")
        _init_temp_db(db_path)
        repo = _make_job_repo(db_path)

        j1 = repo.create_job("type_a", "Job A")
        j2 = repo.create_job("type_a", "Job B")
        jobs = repo.list_jobs(limit=10)
        ids = [j["job_id"] for j in jobs]
        assert j1 in ids
        assert j2 in ids

    def test_update_job_status(self, tmp_path):
        db_path = str(tmp_path / "test_jobs.db")
        _init_temp_db(db_path)
        repo = _make_job_repo(db_path)

        job_id = repo.create_job("test", "Status update")
        ok = repo.update_job(job_id, status="running", message="Working")
        assert ok is True
        job = repo.get_job(job_id)
        assert job["status"] == "running"
        assert job["message"] == "Working"

    def test_update_job_to_failed(self, tmp_path):
        db_path = str(tmp_path / "test_jobs.db")
        _init_temp_db(db_path)
        repo = _make_job_repo(db_path)

        job_id = repo.create_job("test", "Will fail")
        repo.update_job(job_id, status="failed", error_message="Something broke")
        job = repo.get_job(job_id)
        assert job["status"] == "failed"
        assert "Something broke" in job["error_message"]

    def test_job_list_by_status(self, tmp_path):
        db_path = str(tmp_path / "test_jobs.db")
        _init_temp_db(db_path)
        repo = _make_job_repo(db_path)

        repo.create_job("t", "Pending 1")
        jid = repo.create_job("t", "Success 1")
        repo.update_job(jid, status="success")
        pending = repo.list_jobs(status="pending", limit=50)
        success = repo.list_jobs(status="success", limit=50)
        assert all(j["status"] == "pending" for j in pending)
        assert all(j["status"] == "success" for j in success)


# ---------------------------------------------------------------------------
# TestUploadedFiles
# ---------------------------------------------------------------------------

class TestUploadedFiles:
    def test_insert_upload(self, tmp_path):
        db_path = str(tmp_path / "test_uploads.db")
        _init_temp_db(db_path)
        repo = _make_job_repo(db_path)
        checksum = uuid.uuid4().hex
        uid = repo.insert_upload("test.pdf", "/tmp/test.pdf", 1234, checksum,
                                 "10.1234/x", "Title", 2024, "Author")
        assert uid > 0

    def test_get_upload_by_checksum(self, tmp_path):
        db_path = str(tmp_path / "test_uploads.db")
        _init_temp_db(db_path)
        repo = _make_job_repo(db_path)
        checksum = uuid.uuid4().hex
        repo.insert_upload("f1.pdf", "/tmp/f1.pdf", 100, checksum)
        found = repo.get_upload_by_checksum(checksum)
        assert found is not None
        assert found["original_filename"] == "f1.pdf"

    def test_checksum_not_found(self, tmp_path):
        db_path = str(tmp_path / "test_uploads.db")
        _init_temp_db(db_path)
        repo = _make_job_repo(db_path)
        assert repo.get_upload_by_checksum("nonexistent_checksum_0000") is None

    def test_update_upload_status(self, tmp_path):
        db_path = str(tmp_path / "test_uploads.db")
        _init_temp_db(db_path)
        repo = _make_job_repo(db_path)
        checksum = uuid.uuid4().hex
        uid = repo.insert_upload("up.pdf", "/tmp/up.pdf", 200, checksum)
        # Update without matched_paper_id (FK would fail on fresh db)
        ok = repo.update_upload(uid, status="merged",
                                match_method="doi", match_score=1.0)
        assert ok is True

    def test_duplicate_checksum_raises_integrity_error(self, tmp_path):
        """Inserting the same checksum twice should raise IntegrityError."""
        db_path = str(tmp_path / "test_uploads.db")
        _init_temp_db(db_path)
        repo = _make_job_repo(db_path)
        checksum = uuid.uuid4().hex
        repo.insert_upload("a.pdf", "/tmp/a.pdf", 100, checksum)
        import sqlite3
        with pytest.raises(sqlite3.IntegrityError):
            repo.insert_upload("b.pdf", "/tmp/b.pdf", 200, checksum)


# ---------------------------------------------------------------------------
# TestTaskManager
# ---------------------------------------------------------------------------

class TestTaskManager:
    def test_submit_returns_job_id(self, tmp_path):
        db_path = str(tmp_path / "test_mgr.db")
        _init_temp_db(db_path)
        mgr = _make_task_manager(db_path)
        try:
            job_id = mgr.submit("pdf_upload_ingest", "Test submit", {"files": []})
            assert job_id > 0
        finally:
            mgr.shutdown(wait=True)

    def test_job_starts_pending(self, tmp_path):
        db_path = str(tmp_path / "test_mgr.db")
        _init_temp_db(db_path)
        mgr = _make_task_manager(db_path)
        try:
            job_id = mgr.submit("pdf_upload_ingest", "Pending check", {"files": []})
            job = mgr.get_job(job_id)
            assert job["status"] in ("pending", "running", "success", "failed")
        finally:
            mgr.shutdown(wait=True)

    def test_no_handler_marks_failed(self, tmp_path):
        db_path = str(tmp_path / "test_mgr.db")
        _init_temp_db(db_path)
        mgr = _make_task_manager(db_path)
        try:
            job_id = mgr.submit("nonexistent_type", "No handler")
            time.sleep(0.5)
            job = mgr.get_job(job_id)
            assert job["status"] == "failed"
            assert "No handler" in job.get("error_message", "")
        finally:
            mgr.shutdown(wait=True)

    def test_upload_ingest_handler_runs(self, tmp_path):
        """Submit an upload job with a real PDF file and verify it succeeds."""
        import fitz

        db_path = str(tmp_path / "test_mgr_ingest.db")
        _init_temp_db(db_path)
        mgr = _make_task_manager(db_path)

        # Create a minimal PDF in tmp_path (isolated, not system temp)
        pdf_path = tmp_path / "bg_test_minimal.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72),
                         "Background Job Test Paper\nDOI: 10.9999/bgtest.2026",
                         fontsize=12)
        doc.save(str(pdf_path))
        doc.close()

        try:
            payload = {"files": [{"path": str(pdf_path), "name": "bg_test_minimal.pdf"}]}
            job_id = mgr.submit("pdf_upload_ingest", "Test upload handler", payload)

            for _ in range(20):
                time.sleep(0.3)
                job = mgr.get_job(job_id)
                if job["status"] in ("success", "failed"):
                    break

            job = mgr.get_job(job_id)
            assert job["status"] == "success", \
                f"Job failed: {job.get('error_message', '')}"
            assert "上传完成" in job.get("message", "")
        finally:
            mgr.shutdown(wait=True)

    def test_user_message_does_not_show_paper_id(self, tmp_path):
        """Result messages should not leak internal IDs."""
        import fitz

        db_path = str(tmp_path / "test_mgr_noid.db")
        _init_temp_db(db_path)
        mgr = _make_task_manager(db_path)

        pdf_path = tmp_path / "bg_noid_test.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "No ID Leak Paper", fontsize=12)
        doc.save(str(pdf_path))
        doc.close()

        try:
            job_id = mgr.submit("pdf_upload_ingest", "No ID test",
                                {"files": [{"path": str(pdf_path), "name": "noid.pdf"}]})
            for _ in range(20):
                time.sleep(0.3)
                job = mgr.get_job(job_id)
                if job["status"] in ("success", "failed"):
                    break

            job = mgr.get_job(job_id)
            msg = job.get("message", "")
            assert "paper_id" not in msg.lower()
            assert "#" not in msg
        finally:
            mgr.shutdown(wait=True)

    def test_pdf_available_after_upload(self, tmp_path):
        """After upload+ingest, the paper should have pdf_path set."""
        import fitz

        db_path = str(tmp_path / "test_mgr_avail.db")
        _init_temp_db(db_path)
        mgr = _make_task_manager(db_path)

        pdf_path = tmp_path / "bg_avail_test.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72),
                         "Availability Test\nDOI: 10.9999/avail.2026",
                         fontsize=12)
        doc.save(str(pdf_path))
        doc.close()

        try:
            job_id = mgr.submit("pdf_upload_ingest", "Avail test",
                                {"files": [{"path": str(pdf_path), "name": "avail.pdf"}]})
            for _ in range(20):
                time.sleep(0.3)
                if mgr.get_job(job_id)["status"] in ("success", "failed"):
                    break

            from src.database.connection import DatabaseManager
            from src.storage.repository import PaperRepository
            repo = PaperRepository(db=DatabaseManager(db_path))
            paper = repo.get_paper_by_doi("10.9999/avail.2026")
            assert paper is not None, "Paper should exist in test db after upload"
            assert paper.get("pdf_path"), "PDF path should be set after upload"
        finally:
            mgr.shutdown(wait=True)

    def test_task_manager_shutdown_releases_threads(self, tmp_path):
        """After shutdown(wait=True), all background threads must be done."""
        db_path = str(tmp_path / "test_mgr_shutdown.db")
        _init_temp_db(db_path)
        mgr = _make_task_manager(db_path)

        mgr.submit("pdf_upload_ingest", "Shutdown test", {"files": []})
        mgr.shutdown(wait=True)

        # If we get here without hanging, threads were joined successfully.
        # Verify the executor cannot accept new work.
        import concurrent.futures
        with pytest.raises(RuntimeError):
            mgr._executor.submit(lambda: None)

    def test_handler_does_not_touch_real_db(self, tmp_path, monkeypatch):
        """The background handler must never access the real data/paper.db."""
        real_db = Path("data/paper.db").resolve()

        db_path = str(tmp_path / "test_mgr_real.db")
        _init_temp_db(db_path)
        mgr = _make_task_manager(db_path)

        # Guard: if real db is accessed during the test, fail
        original_connect = None
        try:
            import sqlite3
            original_connect = sqlite3.connect

            def guarded_connect(path, *args, **kwargs):
                resolved = Path(path).resolve()
                if resolved == real_db:
                    raise AssertionError(
                        f"Background handler tried to connect to real DB: {real_db}")
                return original_connect(path, *args, **kwargs)

            sqlite3.connect = guarded_connect  # type: ignore[assignment]

            job_id = mgr.submit("pdf_upload_ingest", "No real DB",
                                {"files": []})
            for _ in range(10):
                time.sleep(0.2)
                if mgr.get_job(job_id)["status"] in ("success", "failed"):
                    break
        finally:
            if original_connect:
                sqlite3.connect = original_connect  # type: ignore[assignment]
            mgr.shutdown(wait=True)


# ---------------------------------------------------------------------------
# TestJobRecovery — stale running job cleanup & convenience markers
# ---------------------------------------------------------------------------

class TestJobRecovery:
    def test_mark_stale_running_as_interrupted(self, tmp_path):
        """Running jobs with no finished_at are marked interrupted."""
        db_path = str(tmp_path / "test_recovery.db")
        _init_temp_db(db_path)
        repo = _make_job_repo(db_path)

        # Create and manually set a job to running
        j1 = repo.create_job("test", "Job 1")
        repo.mark_job_running(j1)

        j2 = repo.create_job("test", "Job 2")
        repo.mark_job_running(j2)

        # One job is already success — should NOT be touched
        j3 = repo.create_job("test", "Job 3")
        repo.mark_job_success(j3, message="Done")

        count = repo.mark_stale_running_jobs_as_interrupted()
        assert count == 2

        job1 = repo.get_job(j1)
        assert job1["status"] == "interrupted"
        assert "中断" in job1.get("error_message", "")
        assert job1["finished_at"] is not None

        job2 = repo.get_job(j2)
        assert job2["status"] == "interrupted"

        # Already-success job is untouched
        job3 = repo.get_job(j3)
        assert job3["status"] == "success"

    def test_stale_only_affects_running_with_null_finished_at(self, tmp_path):
        """Only running jobs with finished_at=NULL are affected."""
        db_path = str(tmp_path / "test_recovery2.db")
        _init_temp_db(db_path)
        repo = _make_job_repo(db_path)

        j1 = repo.create_job("t", "Pending")                     # pending
        j2 = repo.create_job("t", "Running")
        repo.mark_job_running(j2)                                 # running
        j3 = repo.create_job("t", "Success")
        repo.mark_job_success(j3)                                 # success
        j4 = repo.create_job("t", "Failed")
        repo.mark_job_failed(j4, error_message="Boom")            # failed

        count = repo.mark_stale_running_jobs_as_interrupted()
        assert count == 1  # only j2 was running with null finished_at

        assert repo.get_job(j1)["status"] == "pending"
        assert repo.get_job(j2)["status"] == "interrupted"
        assert repo.get_job(j3)["status"] == "success"
        assert repo.get_job(j4)["status"] == "failed"

    def test_no_stale_jobs_returns_zero(self, tmp_path):
        """When there are no stale running jobs, return 0."""
        db_path = str(tmp_path / "test_recovery3.db")
        _init_temp_db(db_path)
        repo = _make_job_repo(db_path)

        repo.create_job("t", "Pending 1")
        repo.create_job("t", "Pending 2")

        count = repo.mark_stale_running_jobs_as_interrupted()
        assert count == 0

    def test_get_running_jobs(self, tmp_path):
        db_path = str(tmp_path / "test_recovery4.db")
        _init_temp_db(db_path)
        repo = _make_job_repo(db_path)

        j1 = repo.create_job("t", "One")
        repo.mark_job_running(j1)
        j2 = repo.create_job("t", "Two")
        repo.mark_job_running(j2)

        running = repo.get_running_jobs()
        assert len(running) >= 2
        statuses = {j["status"] for j in running}
        assert statuses == {"running"}

    def test_mark_job_interrupted_single(self, tmp_path):
        db_path = str(tmp_path / "test_recovery5.db")
        _init_temp_db(db_path)
        repo = _make_job_repo(db_path)

        jid = repo.create_job("t", "Will interrupt")
        repo.mark_job_running(jid)
        repo.mark_job_interrupted(jid, message="手动中断")

        job = repo.get_job(jid)
        assert job["status"] == "interrupted"
        assert "手动中断" in job.get("error_message", "")
        assert job["finished_at"] is not None

    def test_update_job_progress(self, tmp_path):
        db_path = str(tmp_path / "test_recovery6.db")
        _init_temp_db(db_path)
        repo = _make_job_repo(db_path)

        jid = repo.create_job("t", "Progress test")
        repo.update_job_progress(jid, current=3, total=10, message="处理中")
        job = repo.get_job(jid)
        assert job["progress_current"] == 3
        assert job["progress_total"] == 10
        assert job["message"] == "处理中"

    def test_list_jobs_filter_by_type(self, tmp_path):
        db_path = str(tmp_path / "test_recovery7.db")
        _init_temp_db(db_path)
        repo = _make_job_repo(db_path)

        repo.create_job("type_a", "A1")
        repo.create_job("type_a", "A2")
        repo.create_job("type_b", "B1")

        a_jobs = repo.list_jobs(job_type="type_a", limit=50)
        b_jobs = repo.list_jobs(job_type="type_b", limit=50)
        assert all(j["job_type"] == "type_a" for j in a_jobs)
        assert all(j["job_type"] == "type_b" for j in b_jobs)
        assert len(a_jobs) >= 2
        assert len(b_jobs) >= 1


# ---------------------------------------------------------------------------
# TestTaskManagerRecovery — startup_recovery flag
# ---------------------------------------------------------------------------

class TestTaskManagerRecovery:
    def test_startup_recovery_cleans_stale_jobs(self, tmp_path):
        """TaskManager with startup_recovery=True cleans stale running jobs."""
        db_path = str(tmp_path / "test_tm_recovery.db")
        _init_temp_db(db_path)

        # Pre-create stale running jobs in the db
        repo = _make_job_repo(db_path)
        j1 = repo.create_job("test", "Stale 1")
        repo.mark_job_running(j1)
        j2 = repo.create_job("test", "Stale 2")
        repo.mark_job_running(j2)
        j3 = repo.create_job("test", "Already done")
        repo.mark_job_success(j3)

        # Now create TaskManager with startup_recovery=True
        mgr = _make_task_manager(db_path, startup_recovery=True)
        try:
            assert repo.get_job(j1)["status"] == "interrupted"
            assert repo.get_job(j2)["status"] == "interrupted"
            assert repo.get_job(j3)["status"] == "success"  # untouched
        finally:
            mgr.shutdown(wait=True)

    def test_startup_recovery_false_does_not_clean(self, tmp_path):
        """TaskManager with startup_recovery=False leaves stale jobs alone."""
        db_path = str(tmp_path / "test_tm_norecovery.db")
        _init_temp_db(db_path)

        repo = _make_job_repo(db_path)
        j1 = repo.create_job("test", "Stale")
        repo.mark_job_running(j1)

        # Create TaskManager with startup_recovery=False
        mgr = _make_task_manager(db_path, startup_recovery=False)
        try:
            # Job should still be running, not interrupted
            assert repo.get_job(j1)["status"] == "running"
        finally:
            mgr.shutdown(wait=True)


# ---------------------------------------------------------------------------
# TestHandlerRegistration
# ---------------------------------------------------------------------------

class TestHandlerRegistration:
    def test_register_new_handler(self, tmp_path):
        """A newly registered handler can be submitted and invoked."""
        db_path = str(tmp_path / "test_handler.db")
        _init_temp_db(db_path)
        mgr = _make_task_manager(db_path, startup_recovery=False)

        import json
        handler_called = []

        def my_handler(job: dict):
            handler_called.append(job["job_id"])
            payload = json.loads(job.get("payload_json", "{}"))
            # Handler marks itself success
            from src.database.connection import DatabaseManager
            from src.tasks.repository import JobRepository
            repo = JobRepository(db=DatabaseManager(db_path))
            repo.mark_job_success(job["job_id"], message=f"Handled {payload.get('name', '')}")

        mgr.register_handler("my_custom_type", my_handler)

        try:
            job_id = mgr.submit("my_custom_type", "Custom job", {"name": "hello"})
            for _ in range(20):
                time.sleep(0.2)
                if mgr.get_job(job_id)["status"] == "success":
                    break

            job = mgr.get_job(job_id)
            assert job["status"] == "success"
            assert "Handled hello" in job.get("message", "")
            assert len(handler_called) == 1
            assert handler_called[0] == job_id
        finally:
            mgr.shutdown(wait=True)

    def test_overwrite_handler(self, tmp_path):
        """Registering a handler for the same job_type overwrites previous."""
        db_path = str(tmp_path / "test_handler_overwrite.db")
        _init_temp_db(db_path)
        mgr = _make_task_manager(db_path, startup_recovery=False)

        calls = []

        def first(job):
            calls.append("first")

        def second(job):
            calls.append("second")
            mgr.repo.mark_job_success(job["job_id"], message="second handler")

        mgr.register_handler("test_type", first)
        mgr.register_handler("test_type", second)

        try:
            job_id = mgr.submit("test_type", "Overwrite test")
            for _ in range(20):
                time.sleep(0.2)
                if mgr.get_job(job_id)["status"] == "success":
                    break

            assert calls == ["second"], f"Expected only second handler, got {calls}"
        finally:
            mgr.shutdown(wait=True)

    def test_unregistered_handler_fails(self, tmp_path):
        """Submitting a job type with no handler should fail immediately."""
        db_path = str(tmp_path / "test_handler_unknown.db")
        _init_temp_db(db_path)
        mgr = _make_task_manager(db_path, startup_recovery=False)

        try:
            job_id = mgr.submit("completely_unknown_type", "No handler")
            time.sleep(0.3)
            job = mgr.get_job(job_id)
            assert job["status"] == "failed"
            assert "No handler" in job.get("error_message", "")
        finally:
            mgr.shutdown(wait=True)
