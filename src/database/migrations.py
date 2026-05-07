"""
数据库迁移管理 — 按版本号顺序执行 SQL 迁移脚本。

迁移脚本存放于 migrations/ 目录，命名格式：
  v{NN}_{description}.sql

如：v01_initial_schema.sql, v02_add_fts.sql
"""

import sqlite3
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger(__name__)

# migrations 目录
_MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "migrations"


def get_applied_versions(conn: sqlite3.Connection) -> set[int]:
    """
    获取已应用的迁移版本号集合。

    Args:
        conn: 数据库连接

    Returns:
        已应用的版本号集合
    """
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT version FROM schema_version ORDER BY version")
        return {row[0] for row in cursor.fetchall()}
    except sqlite3.OperationalError:
        # schema_version 表还不存在
        return set()


def get_pending_migrations(applied_versions: set[int]) -> list[Path]:
    """
    获取待执行的迁移文件列表（按版本号排序）。

    Args:
        applied_versions: 已应用版本号集合

    Returns:
        排序后的迁移文件路径列表
    """
    if not _MIGRATIONS_DIR.exists():
        logger.debug(f"迁移目录不存在: {_MIGRATIONS_DIR}")
        return []

    pending = []
    for sql_file in sorted(_MIGRATIONS_DIR.glob("v[0-9][0-9]_*.sql")):
        # 解析版本号：v01_initial_schema.sql → 1
        try:
            version_str = sql_file.stem[1:3]  # 取 "01" 部分
            version = int(version_str)
            if version not in applied_versions:
                pending.append(sql_file)
        except (ValueError, IndexError):
            logger.warning(f"无法解析迁移文件版本号: {sql_file.name}")
            continue

    return sorted(pending, key=lambda p: p.stem)


def apply_pending_migrations(conn: sqlite3.Connection) -> int:
    """
    执行所有待应用的迁移脚本。

    Args:
        conn: 数据库连接

    Returns:
        本次执行的迁移数量
    """
    applied = get_applied_versions(conn)
    pending = get_pending_migrations(applied)

    if not pending:
        logger.info("没有待执行的迁移脚本。")
        return 0

    logger.info(f"发现 {len(pending)} 个待执行的迁移脚本。")
    cursor = conn.cursor()

    for sql_file in pending:
        # 解析版本号
        version = int(sql_file.stem[1:3])
        description = sql_file.stem[4:].replace("_", " ")

        logger.info(f"执行迁移 v{version}: {description}")

        # 读取并执行 SQL
        sql_content = sql_file.read_text(encoding="utf-8")
        try:
            cursor.executescript(sql_content)
            cursor.execute(
                "INSERT OR REPLACE INTO schema_version (version, description) VALUES (?, ?)",
                (version, description),
            )
            conn.commit()
            logger.info(f"迁移 v{version} 执行成功。")
        except Exception as e:
            logger.error(f"迁移 v{version} 执行失败: {e}")
            conn.rollback()
            raise

    return len(pending)
