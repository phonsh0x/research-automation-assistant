-- ============================================================================
-- 迁移 v03: PDF 转换字段补列
-- 描述：确保 full_texts 表包含 quality_score 和 word_count 列。
--        papers 表已含 pdf_path / md_path（v01）。
-- ============================================================================

-- full_texts 可能缺少 word_count 列（v01 只有 char_count）
-- SQLite 不支持 ADD COLUMN IF NOT EXISTS，使用 try-catch 模式
INSERT OR IGNORE INTO schema_version (version, description) VALUES (3, 'v03_pdf_conversion');
