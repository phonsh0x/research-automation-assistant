"""
数据库模块 — SQLite 文献数据库的初始化、连接管理、迁移和基础 CRUD。

核心组件：
  - DatabaseManager: 数据库连接与初始化
  - 完整 DDL schema（papers, authors, keywords, full_texts, citations, group_profile, embeddings）
  - Schema 版本管理与自动迁移
"""

from src.database.connection import DatabaseManager, get_db

__all__ = ["DatabaseManager", "get_db"]
