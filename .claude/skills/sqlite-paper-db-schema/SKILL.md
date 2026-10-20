---
name: sqlite-paper-db-schema
description: SQLite 文献数据库模式设计与维护。定义数据库表结构、索引、视图和迁移脚本，统一管理论文元数据、全文、向量嵌入、课题组论文等核心数据。触发于数据库初始化、schema 变更、数据导入导出、查询优化。
when_to_use:
  - 初始化或重建 literature 数据库（data/paper.db）
  - 定义或修改数据库表结构
  - 编写数据导入/导出脚本
  - 优化文献查询性能（索引、视图）
  - 数据库迁移（schema 版本升级）
  - 设计向量嵌入的存储与关联方式
---

# sqlite-paper-db-schema — SQLite 文献数据库模式

## 角色定位

你是"SQLite 文献数据库"的设计和维护者。SQLite 数据库默认路径为 `data/paper.db`，是科研助手系统的数据中枢，连接检索、转换、RAG、画像、写作各模块。

## 数据库路径

- 默认：`data/paper.db`
- 可通过环境变量 `PAPER_DB_PATH` 覆盖。
- SQLite 推荐设置：`journal_mode=WAL`, `foreign_keys=ON`。

## 完整 DDL

### 核心表

```sql
-- 文献主表
CREATE TABLE IF NOT EXISTS papers (
    paper_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    abstract        TEXT,
    doi             TEXT UNIQUE,
    arxiv_id        TEXT UNIQUE,
    pmid            TEXT UNIQUE,
    pmcid           TEXT UNIQUE,
    year            INTEGER,
    journal         TEXT,
    volume          TEXT,
    issue           TEXT,
    pages           TEXT,
    publisher       TEXT,
    language        TEXT DEFAULT 'en',
    citation_count  INTEGER DEFAULT 0,
    oa_status       TEXT,           -- gold/green/hybrid/bronze/closed
    pdf_path        TEXT,           -- 相对路径 data/pdf/xxx.pdf
    md_path         TEXT,           -- 相对路径 data/markdown/xxx.md
    source_api      TEXT,           -- 来源：openalex/crossref/pubmed/arxiv
    source_id       TEXT,           -- 来源系统中的 ID
    is_group_paper  INTEGER DEFAULT 0,  -- 是否为课题组论文
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 作者表
CREATE TABLE IF NOT EXISTS authors (
    author_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    orcid       TEXT UNIQUE,
    affiliation TEXT,
    h_index     INTEGER,
    UNIQUE(name, orcid)
);

-- 论文-作者关联（支持作者顺序）
CREATE TABLE IF NOT EXISTS paper_authors (
    paper_id    INTEGER NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
    author_id   INTEGER NOT NULL REFERENCES authors(author_id) ON DELETE CASCADE,
    author_order INTEGER DEFAULT 1,
    is_corresponding INTEGER DEFAULT 0,
    PRIMARY KEY (paper_id, author_id)
);

-- 关键词表（统一词汇表）
CREATE TABLE IF NOT EXISTS keywords (
    keyword_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword     TEXT UNIQUE NOT NULL,
    language    TEXT DEFAULT 'en'   -- en/zh
);

-- 论文-关键词关联
CREATE TABLE IF NOT EXISTS paper_keywords (
    paper_id    INTEGER NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
    keyword_id  INTEGER NOT NULL REFERENCES keywords(keyword_id) ON DELETE CASCADE,
    is_author_kw INTEGER DEFAULT 0,  -- 1=作者提供关键词，0=自动抽取
    PRIMARY KEY (paper_id, keyword_id)
);

-- 全文 Markdown 内容
CREATE TABLE IF NOT EXISTS full_texts (
    paper_id    INTEGER PRIMARY KEY REFERENCES papers(paper_id) ON DELETE CASCADE,
    content     TEXT NOT NULL,         -- 完整 Markdown 正文
    section_count INTEGER DEFAULT 0,  -- 章节数
    figure_count  INTEGER DEFAULT 0,  -- 图表数
    table_count   INTEGER DEFAULT 0,  -- 表格数
    equation_count INTEGER DEFAULT 0, -- 公式数
    ref_count     INTEGER DEFAULT 0,  -- 参考文献数
    char_count    INTEGER DEFAULT 0,  -- 总字符数
    extracted_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 参考文献引用关系
CREATE TABLE IF NOT EXISTS citations (
    citing_paper_id INTEGER NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
    cited_doi       TEXT,
    cited_title     TEXT,
    cited_year      INTEGER,
    citation_context TEXT,            -- 引用上下文
    PRIMARY KEY (citing_paper_id, cited_doi)
);

-- 课题组论文画像
CREATE TABLE IF NOT EXISTS group_profile (
    profile_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id      INTEGER NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
    research_area TEXT,               -- 研究方向标签
    method_tags   TEXT,               -- 方法标签（JSON 数组）
    domain_tags   TEXT,               -- 领域标签（JSON 数组）
    contribution  TEXT,               -- 主要贡献简述
    generated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 向量嵌入表

```sql
-- 向量嵌入元数据（实际向量存储在 ChromaDB 中）
CREATE TABLE IF NOT EXISTS embeddings (
    embed_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id      INTEGER NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
    chunk_index   INTEGER NOT NULL,          -- 分块序号
    chunk_text    TEXT NOT NULL,             -- 分块原文
    chunk_type    TEXT DEFAULT 'paragraph',  -- paragraph/section/abstract/title
    section_title TEXT,                      -- 所在章节标题
    embed_model   TEXT NOT NULL,             -- 嵌入模型名称
    embed_dim     INTEGER NOT NULL,          -- 嵌入维度
    chroma_id     TEXT UNIQUE,               -- ChromaDB 中的对应 ID
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(paper_id, chunk_index)
);
```

### 视图

```sql
-- 论文完整信息视图
CREATE VIEW IF NOT EXISTS v_paper_full AS
SELECT
    p.paper_id, p.title, p.abstract, p.doi, p.year, p.journal,
    p.citation_count, p.oa_status, p.pdf_path, p.md_path,
    p.is_group_paper,
    GROUP_CONCAT(DISTINCT a.name ORDER BY pa.author_order) AS authors,
    GROUP_CONCAT(DISTINCT k.keyword) AS keywords
FROM papers p
LEFT JOIN paper_authors pa ON p.paper_id = pa.paper_id
LEFT JOIN authors a ON pa.author_id = a.author_id
LEFT JOIN paper_keywords pk ON p.paper_id = pk.paper_id
LEFT JOIN keywords k ON pk.keyword_id = k.keyword_id
GROUP BY p.paper_id;

-- 课题组论文视图
CREATE VIEW IF NOT EXISTS v_group_papers AS
SELECT * FROM v_paper_full WHERE is_group_paper = 1;

-- 可获取全文的论文
CREATE VIEW IF NOT EXISTS v_fulltext_available AS
SELECT * FROM v_paper_full WHERE md_path IS NOT NULL;
```

### 索引

```sql
CREATE INDEX IF NOT EXISTS idx_papers_doi       ON papers(doi);
CREATE INDEX IF NOT EXISTS idx_papers_year      ON papers(year);
CREATE INDEX IF NOT EXISTS idx_papers_journal   ON papers(journal);
CREATE INDEX IF NOT EXISTS idx_papers_oa_status ON papers(oa_status);
CREATE INDEX IF NOT EXISTS idx_papers_group     ON papers(is_group_paper);
CREATE INDEX IF NOT EXISTS idx_papers_title_ft  ON papers(title);
CREATE INDEX IF NOT EXISTS idx_authors_name     ON authors(name);
CREATE INDEX IF NOT EXISTS idx_keywords_kw      ON keywords(keyword);
CREATE INDEX IF NOT EXISTS idx_embeddings_paper ON embeddings(paper_id);
CREATE INDEX IF NOT EXISTS idx_full_texts_ft    ON full_texts(content);
```

## 初始化与迁移

### 首次初始化

```python
import sqlite3
from pathlib import Path

DB_PATH = Path("data/paper.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(str(DB_PATH))
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA foreign_keys=ON")
# 执行上述 DDL...
conn.close()
```

### Schema 版本管理

在数据库中维护 `schema_version` 表：

```sql
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);
```

迁移脚本命名：`migrations/v{NN}_{description}.sql`，按序执行。在代码中检查当前 schema 版本，自动应用未执行的迁移。

## 常用查询模板

### 按关键词检索

```sql
SELECT p.* FROM papers p
JOIN paper_keywords pk ON p.paper_id = pk.paper_id
JOIN keywords k ON pk.keyword_id = k.keyword_id
WHERE k.keyword LIKE '%deep learning%' AND p.year >= 2020
ORDER BY p.citation_count DESC LIMIT 50;
```

### 完整全文搜索（整合 FTS5）

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
    title, abstract, content=full_texts, content_rowid=paper_id
);
```

### 统计查询

```sql
-- 各年份论文数量
SELECT year, COUNT(*) FROM papers GROUP BY year ORDER BY year;

-- 各 OA 状态分布
SELECT oa_status, COUNT(*) FROM papers GROUP BY oa_status;

-- 课题组研究方向分布
SELECT research_area, COUNT(*) FROM group_profile GROUP BY research_area;
```

## 数据导入/导出

- **导入**：支持从 CSV、JSON、BibTeX 批量导入文献元数据。
- **导出**：支持导出为 BibTeX（`.bib`）、CSV、JSON 格式。
- 导入时自动去重（按 DOI），保留已有数据优先。
