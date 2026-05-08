-- ============================================================================
-- 迁移 v04: 后台任务 + PDF 上传收件箱
-- ============================================================================

CREATE TABLE IF NOT EXISTS background_jobs (
    job_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type        TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    title           TEXT,
    payload_json    TEXT,
    result_json     TEXT,
    progress_current INTEGER DEFAULT 0,
    progress_total  INTEGER DEFAULT 0,
    message         TEXT,
    error_message   TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at      TIMESTAMP,
    finished_at     TIMESTAMP
);

CREATE TABLE IF NOT EXISTS uploaded_files (
    upload_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    original_filename   TEXT,
    stored_path         TEXT,
    file_size           INTEGER DEFAULT 0,
    checksum_sha256     TEXT UNIQUE,
    detected_doi        TEXT,
    detected_title      TEXT,
    detected_year       INTEGER,
    detected_authors    TEXT,
    matched_paper_id    INTEGER REFERENCES papers(paper_id),
    match_method        TEXT,
    match_score         REAL DEFAULT 0,
    status              TEXT DEFAULT 'staged',
    error_message       TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO schema_version (version, description) VALUES (4, 'v04_background_jobs_and_uploads');
