"""
文献检索模块 — 通过合法 API（OpenAlex、Crossref、PubMed、arXiv 等）检索学术文献。

职责：
  - 按关键词构建查询并调用外部 API
  - 将不同 API 返回的结果标准化为统一格式
  - 对检索结果按 DOI 去重
  - 查询 Unpaywall API 确定文献的开放获取状态

开放 API 来源（合法）：
  - OpenAlex API（开放文献索引）
  - Crossref API（DOI 元数据查询）
  - PubMed / PubMed Central Entrez API
  - arXiv API（预印本）
  - Semantic Scholar API
  - Unpaywall API（OA 状态查询）

严禁使用：Sci-Hub、Library Genesis 或任何绕过付费墙的手段。
"""

from src.paper_search.models import PaperMetadata
from src.paper_search.searcher import PaperSearcher

__all__ = ["PaperMetadata", "PaperSearcher"]
