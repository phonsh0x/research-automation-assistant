"""
数据库迁移管理 — 按版本号顺序执行 SQL 迁移脚本。

迁移脚本存放于 migrations/ 目录，命名格式：
  v{NN}_{description}.sql

如：v01_initial_schema.sql, v02_add_fts.sql
"""

import re
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


def _strip_block_comments(sql_content: str) -> str:
    """
    移除 SQL 文本中的 /* ... */ 块注释。

    Args:
        sql_content: 原始 SQL 文本

    Returns:
        移除块注释后的文本
    """
    result: list[str] = []
    in_block = False
    for line in sql_content.split("\n"):
        if in_block:
            if "*/" in line:
                in_block = False
                # 处理 */ 之后可能还有内容
                after = line.split("*/", 1)[1] if "*/" in line else ""
                if after.strip():
                    result.append(after)
            continue
        if "/*" in line:
            before = line.split("/*", 1)[0]
            if before.strip():
                result.append(before)
            if "*/" in line:
                # 单行块注释
                after = line.split("*/", 1)[1] if "*/" in line else ""
                if after.strip():
                    result.append(after)
            else:
                in_block = True
            continue
        result.append(line)
    return "\n".join(result)


def _split_sql_statements(sql_content: str) -> list[str]:
    """
    将包含多条 SQL 语句的文本拆分为单独的语句列表。

    拆分策略：先移除块注释，再按行扫描，以 ; 结尾的行为语句终止符。
    跳过纯注释行（以 -- 开头）和空行。

    Args:
        sql_content: 完整的 SQL 文本

    Returns:
        语句字符串列表
    """
    # 预处理：移除 /* ... */ 块注释
    cleaned = _strip_block_comments(sql_content)

    statements = []
    buffer: list[str] = []

    for line in cleaned.split("\n"):
        stripped = line.strip()

        # 跳过纯注释行和空行
        if not stripped or stripped.startswith("--"):
            # buffer 已有内容时保留空行（SQL 语句内部换行），但不保留 -- 注释
            if buffer and not stripped:
                buffer.append(line)
            continue

        buffer.append(line)

        # 以 ; 结尾视为语句结束
        if stripped.rstrip().endswith(";"):
            stmt = "\n".join(buffer).strip()
            # 去掉末尾的分号（cursor.execute 不需要）
            if stmt.endswith(";"):
                stmt = stmt[:-1].strip()
            if stmt:
                statements.append(stmt)
            buffer = []

    # 残留内容（最后一条语句可能缺少分号）
    if buffer:
        stmt = "\n".join(buffer).strip()
        if stmt:
            statements.append(stmt)

    return statements


def _is_duplicate_column_error(error: sqlite3.OperationalError) -> bool:
    """
    判断是否为 ALTER TABLE ADD COLUMN 重复列错误。

    Args:
        error: sqlite3.OperationalError 异常

    Returns:
        True 表示是重复列错误
    """
    msg = str(error).lower()
    return "duplicate column" in msg or "has no column named" not in msg and "duplicate" in msg


def apply_pending_migrations(conn: sqlite3.Connection) -> int:
    """
    执行所有待应用的迁移脚本。

    每个迁移脚本中的 SQL 语句逐条执行，以便捕获并跳过
    ALTER TABLE ADD COLUMN 的重复列错误（sqlite3.OperationalError）。

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

        # 读取并逐条执行 SQL
        sql_content = sql_file.read_text(encoding="utf-8")
        statements = _split_sql_statements(sql_content)

        try:
            for stmt in statements:
                stmt = stmt.strip()
                if not stmt:
                    continue
                try:
                    logger.debug(f"  执行语句: {stmt[:80]}...")
                    cursor.execute(stmt)
                except sqlite3.OperationalError as e:
                    msg = str(e).lower()
                    if "duplicate column" in msg:
                        logger.debug(f"  跳过已存在的列: {e}")
                        continue
                    else:
                        raise

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
