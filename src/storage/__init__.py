"""
数据入库模块 — 将检索结果和转换后的 Markdown 写入 SQLite 数据库。

职责：
  - 论文元数据入库（去重、更新）
  - 全文 Markdown 内容入库
  - 作者/关键词关联表维护
  - 数据导出（BibTeX、CSV、JSON）
  - 数据导入（CSV、BibTeX）
"""

from src.storage.repository import PaperRepository

__all__ = ["PaperRepository"]
