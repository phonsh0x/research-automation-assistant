-- ============================================================================
-- 迁移 v02: 全文获取记录表 + 补充 papers 表字段
-- 描述：创建 fulltext_access 表记录全文获取尝试，并在 papers 表添加
--       download_status / access_source / legal_status / pdf_url 字段。
-- ============================================================================

-- UP ----------------------------------------------------------------------

-- 全文获取记录表
CREATE TABLE IF NOT EXISTS fulltext_access (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id          INTEGER NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
    doi               TEXT,
    title             TEXT,
    access_status     TEXT NOT NULL DEFAULT 'unavailable',
    access_source     TEXT,
    access_mode       TEXT DEFAULT 'api',
    legal_status      TEXT NOT NULL DEFAULT 'unknown',
    pdf_url           TEXT,
    landing_page_url  TEXT,
    pdf_path          TEXT,
    file_size         INTEGER DEFAULT 0,
    checksum_sha256   TEXT,
    content_type      TEXT,
    risk_level        TEXT DEFAULT 'low',
    risk_note         TEXT,
    error_message     TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_fulltext_paper    ON fulltext_access(paper_id);
CREATE INDEX IF NOT EXISTS idx_fulltext_doi      ON fulltext_access(doi);
CREATE INDEX IF NOT EXISTS idx_fulltext_status   ON fulltext_access(access_status);
CREATE INDEX IF NOT EXISTS idx_fulltext_source   ON fulltext_access(access_source);
CREATE INDEX IF NOT EXISTS idx_fulltext_legal    ON fulltext_access(legal_status);

-- 补充 papers 表字段（迁移引擎捕获 duplicate column 错误后自动跳过）
ALTER TABLE papers ADD COLUMN download_status TEXT DEFAULT 'pending';
ALTER TABLE papers ADD COLUMN access_source TEXT;
ALTER TABLE papers ADD COLUMN legal_status TEXT DEFAULT 'unknown';
ALTER TABLE papers ADD COLUMN pdf_url TEXT;
ALTER TABLE papers ADD COLUMN error_message TEXT;

-- DOWN --------------------------------------------------------------------
-- 回滚到 v01 时需要移除 v02 新增的内容。
-- 说明：SQLite 不支持 DROP COLUMN，回滚需要重建表或使用 PRAGMA table_info 配合
--       ALTER TABLE RENAME 方式处理。此处提供逻辑步骤，实际回滚需在 Python 层实现。
--
-- 删除 fulltext_access 表及索引:
--   DROP TABLE IF EXISTS fulltext_access;
--
-- papers 表回滚（SQLite 不支持直接 DROP COLUMN，需重建）:
--   ALTER TABLE papers RENAME TO papers_old;
--   CREATE TABLE papers (... 不含 v02 字段 ...);
--   INSERT INTO papers SELECT ... FROM papers_old;
--   DROP TABLE papers_old;
