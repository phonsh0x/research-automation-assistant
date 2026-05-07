"""
数据库连接管理 — 提供 SQLite 连接工厂和单例 DatabaseManager。

特性：
  - 默认路径 data/paper.db
  - 支持环境变量 PAPER_ASSIST_DATABASE_PATH 覆盖
  - 开启 WAL 模式 + 外键约束
  - 连接池（SQLite 单连接 + 线程锁保护）
  - 自动执行 schema 迁移
"""

import sqlite3
import threading
from pathlib import Path
from typing import Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)

# 项目根目录
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class DatabaseManager:
    """
    SQLite 数据库管理器（单例模式）。

    负责：
      - 创建数据库连接
      - 初始化表结构（DDL）
      - Schema 版本管理与迁移

    Usage:
        db = DatabaseManager()
        db.initialize()
        with db.get_cursor() as cur:
            cur.execute("SELECT ...")
    """

    def __init__(self, db_path: Optional[str | Path] = None):
        """
        初始化数据库管理器。

        Args:
            db_path: SQLite 数据库文件路径，默认从配置文件读取。
        """
        if db_path is None:
            db_path = self._resolve_db_path()

        if isinstance(db_path, str):
            db_path = Path(db_path)

        self.db_path = db_path
        # 确保父目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialized = False

        logger.info(f"数据库管理器已创建，目标路径: {self.db_path}")

    @staticmethod
    def _resolve_db_path() -> Path:
        """从配置文件/环境变量中解析数据库路径。"""
        import os

        # 1. 环境变量优先
        env_path = os.environ.get("PAPER_ASSIST_DATABASE_PATH")
        if env_path:
            logger.info(f"使用环境变量指定的数据库路径: {env_path}")
            return Path(env_path)

        # 2. 配置文件
        try:
            from src.config import get_config
            cfg_path = get_config("database.path")
            if cfg_path:
                full_path = _PROJECT_ROOT / cfg_path
                logger.info(f"使用配置文件指定的数据库路径: {full_path}")
                return full_path
        except Exception as e:
            logger.debug(f"从配置文件解析数据库路径失败，使用默认路径: {e}")

        # 3. 默认路径
        default = _PROJECT_ROOT / "data" / "paper.db"
        logger.info(f"使用默认数据库路径: {default}")
        return default

    def get_connection(self) -> sqlite3.Connection:
        """
        获取数据库连接。

        每次调用创建新连接（SQLite 推荐做法：线程各自维护连接）。
        """
        conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,  # 允许多线程使用
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def initialize(self) -> bool:
        """
        初始化数据库：执行建表 DDL 和 schema 迁移。

        如果数据库已初始化，则跳过（幂等操作）。

        Returns:
            True 表示初始化成功或已初始化。
        """
        with self._lock:
            if self._initialized:
                logger.info("数据库已经初始化，跳过。")
                return True

            logger.info("开始初始化数据库...")
            conn = self.get_connection()
            try:
                self._create_tables(conn)
                self._apply_migrations(conn)
                conn.commit()
                self._initialized = True
                logger.info("数据库初始化完成。")
                return True
            except Exception as e:
                logger.error(f"数据库初始化失败: {e}")
                conn.rollback()
                raise
            finally:
                conn.close()

    def _create_tables(self, conn: sqlite3.Connection) -> None:
        """执行完整的建表 DDL。"""
        ddl_statements = _get_ddl()
        cursor = conn.cursor()
        for stmt in ddl_statements:
            statement = stmt.strip()
            if statement:
                logger.debug(f"执行 DDL: {statement[:80]}...")
                cursor.execute(statement)

    def _apply_migrations(self, conn: sqlite3.Connection) -> None:
        """
        执行待应用的 schema 迁移脚本。

        迁移脚本位于 migrations/ 目录，按版本号顺序执行。
        """
        from src.database.migrations import apply_pending_migrations
        apply_pending_migrations(conn)

    def reset(self) -> None:
        """
        重置数据库（删除所有表和数据）。

        警告：此操作不可逆！仅用于开发环境。
        """
        with self._lock:
            if self.db_path.exists():
                self.db_path.unlink()
                self._initialized = False
                logger.warning("数据库已重置（文件已删除）。")

    def get_cursor(self):
        """
        上下文管理器：自动管理连接和游标生命周期。

        Usage:
            db = DatabaseManager()
            with db.get_cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM papers")
        """
        from contextlib import contextmanager

        @contextmanager
        def cursor_context():
            conn = self.get_connection()
            try:
                yield conn.cursor()
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

        return cursor_context()

    @property
    def is_initialized(self) -> bool:
        """数据库是否已完成初始化。"""
        return self._initialized


def _get_ddl() -> list[str]:
    """
    返回完整的数据库 DDL 语句列表。

    表结构参考 sqlite-paper-db-schema skill 规范。
    """
    return [
        # --- Schema 版本管理 ---
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version     INTEGER PRIMARY KEY,
            applied_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            description TEXT
        )
        """,

        # --- 文献主表 ---
        """
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
            oa_status       TEXT,
            pdf_path        TEXT,
            md_path         TEXT,
            source_api      TEXT,
            source_id       TEXT,
            is_group_paper  INTEGER DEFAULT 0,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,

        # --- 作者表 ---
        """
        CREATE TABLE IF NOT EXISTS authors (
            author_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            orcid       TEXT UNIQUE,
            affiliation TEXT,
            h_index     INTEGER,
            UNIQUE(name, orcid)
        )
        """,

        # --- 论文-作者关联 ---
        """
        CREATE TABLE IF NOT EXISTS paper_authors (
            paper_id         INTEGER NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
            author_id        INTEGER NOT NULL REFERENCES authors(author_id) ON DELETE CASCADE,
            author_order     INTEGER DEFAULT 1,
            is_corresponding INTEGER DEFAULT 0,
            PRIMARY KEY (paper_id, author_id)
        )
        """,

        # --- 关键词表 ---
        """
        CREATE TABLE IF NOT EXISTS keywords (
            keyword_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword     TEXT UNIQUE NOT NULL,
            language    TEXT DEFAULT 'en'
        )
        """,

        # --- 论文-关键词关联 ---
        """
        CREATE TABLE IF NOT EXISTS paper_keywords (
            paper_id     INTEGER NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
            keyword_id   INTEGER NOT NULL REFERENCES keywords(keyword_id) ON DELETE CASCADE,
            is_author_kw INTEGER DEFAULT 0,
            PRIMARY KEY (paper_id, keyword_id)
        )
        """,

        # --- 全文 Markdown 内容 ---
        """
        CREATE TABLE IF NOT EXISTS full_texts (
            paper_id       INTEGER PRIMARY KEY REFERENCES papers(paper_id) ON DELETE CASCADE,
            content        TEXT NOT NULL,
            section_count  INTEGER DEFAULT 0,
            figure_count   INTEGER DEFAULT 0,
            table_count    INTEGER DEFAULT 0,
            equation_count INTEGER DEFAULT 0,
            ref_count      INTEGER DEFAULT 0,
            char_count     INTEGER DEFAULT 0,
            extracted_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,

        # --- 参考文献引用关系 ---
        """
        CREATE TABLE IF NOT EXISTS citations (
            citing_paper_id  INTEGER NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
            cited_doi        TEXT,
            cited_title      TEXT,
            cited_year       INTEGER,
            citation_context TEXT,
            PRIMARY KEY (citing_paper_id, cited_doi)
        )
        """,

        # --- 课题组论文画像 ---
        """
        CREATE TABLE IF NOT EXISTS group_profile (
            profile_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id      INTEGER NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
            research_area TEXT,
            method_tags   TEXT,
            domain_tags   TEXT,
            contribution  TEXT,
            generated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,

        # --- 向量嵌入元数据 ---
        """
        CREATE TABLE IF NOT EXISTS embeddings (
            embed_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id      INTEGER NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
            chunk_index   INTEGER NOT NULL,
            chunk_text    TEXT NOT NULL,
            chunk_type    TEXT DEFAULT 'paragraph',
            section_title TEXT,
            embed_model   TEXT NOT NULL,
            embed_dim     INTEGER NOT NULL,
            chroma_id     TEXT UNIQUE,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(paper_id, chunk_index)
        )
        """,

        # --- 索引 ---
        """CREATE INDEX IF NOT EXISTS idx_papers_doi       ON papers(doi)""",
        """CREATE INDEX IF NOT EXISTS idx_papers_year      ON papers(year)""",
        """CREATE INDEX IF NOT EXISTS idx_papers_journal   ON papers(journal)""",
        """CREATE INDEX IF NOT EXISTS idx_papers_oa_status ON papers(oa_status)""",
        """CREATE INDEX IF NOT EXISTS idx_papers_group     ON papers(is_group_paper)""",
        """CREATE INDEX IF NOT EXISTS idx_papers_title_ft  ON papers(title)""",
        """CREATE INDEX IF NOT EXISTS idx_authors_name     ON authors(name)""",
        """CREATE INDEX IF NOT EXISTS idx_keywords_kw      ON keywords(keyword)""",
        """CREATE INDEX IF NOT EXISTS idx_embeddings_paper ON embeddings(paper_id)""",
        """CREATE INDEX IF NOT EXISTS idx_full_texts_ft    ON full_texts(content)""",

        # --- 视图 ---
        """
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
        GROUP BY p.paper_id
        """,

        """
        CREATE VIEW IF NOT EXISTS v_group_papers AS
        SELECT * FROM v_paper_full WHERE is_group_paper = 1
        """,

        """
        CREATE VIEW IF NOT EXISTS v_fulltext_available AS
        SELECT * FROM v_paper_full WHERE md_path IS NOT NULL
        """,
    ]


# 全局单例
_db_manager: Optional[DatabaseManager] = None


def get_db(db_path: Optional[str | Path] = None) -> DatabaseManager:
    """
    获取全局 DatabaseManager 单例。

    Args:
        db_path: 数据库路径（仅在首次调用时生效）

    Returns:
        DatabaseManager 实例
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(db_path)
    return _db_manager
