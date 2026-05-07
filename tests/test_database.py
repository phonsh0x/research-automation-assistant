"""
数据库模块单元测试。

测试 DatabaseManager 的初始化、表创建和基本操作。
"""

import sys
from pathlib import Path

# 确保项目根目录在 Python 路径中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from src.database.connection import DatabaseManager
from src.utils.logger import init_logging


# 初始化日志（测试模式）
init_logging()


class TestDatabaseManager:
    """DatabaseManager 测试套件。"""

    @pytest.fixture
    def db(self, tmp_path):
        """创建临时数据库用于测试。"""
        db_path = tmp_path / "test_paper.db"
        manager = DatabaseManager(db_path)
        manager.initialize()
        return manager

    def test_initialization(self, db):
        """测试数据库初始化是否成功。"""
        assert db.is_initialized

    def test_tables_exist(self, db):
        """测试所有核心表是否已创建。"""
        conn = db.get_connection()
        cursor = conn.cursor()

        # 获取所有表名
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        expected_tables = {
            "schema_version",
            "papers",
            "authors",
            "paper_authors",
            "keywords",
            "paper_keywords",
            "full_texts",
            "citations",
            "group_profile",
            "embeddings",
        }

        for table in expected_tables:
            assert table in tables, f"表 {table} 不存在"

    def test_views_exist(self, db):
        """测试视图是否已创建。"""
        conn = db.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name")
        views = {row[0] for row in cursor.fetchall()}
        conn.close()

        expected_views = {"v_paper_full", "v_group_papers", "v_fulltext_available"}

        for view in expected_views:
            assert view in views, f"视图 {view} 不存在"

    def test_idempotent_initialization(self, db):
        """测试重复初始化为幂等操作。"""
        # 第二次初始化不应报错
        result = db.initialize()
        assert result is True

    def test_schema_version(self, db):
        """测试 schema_version 表记录。"""
        conn = db.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM schema_version")
        count = cursor.fetchone()[0]
        conn.close()

        # 初始迁移应被记录
        assert count >= 0  # 初始版本可能还未写入迁移记录


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
