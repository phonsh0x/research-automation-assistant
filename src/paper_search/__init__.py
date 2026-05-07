"""
文献检索模块 — 通过合法 API（OpenAlex、Crossref、PubMed 等）检索学术文献。

职责：
  - 按关键词构建查询并调用外部 API
  - 将不同 API 返回的结果标准化为统一格式
  - 对检索结果按 DOI 去重
  - 查询 Unpaywall API 确定文献的开放获取状态

开放 API 来源（合法）：
  - OpenAlex API（开放文献索引）
  - Crossref API（DOI 元数据查询）
  - PubMed / PubMed Central Entrez API
  - Europe PMC REST API
  - RSS Feed（期刊最新论文）
  - arXiv API（预印本，预留）
  - Semantic Scholar API（预留）
  - Unpaywall API（OA 状态查询）

严禁使用：Sci-Hub、Library Genesis 或任何绕过付费墙的手段。
"""

# 数据模型
from src.paper_search.models import PaperMetadata, SearchQuery

# 检索器（向后兼容包装）
from src.paper_search.searcher import PaperSearcher, SearchResult

# 抽象基类
from src.paper_search.base import BaseSearcher

# 具体检索源
from src.paper_search.openalex import OpenAlexSearcher
from src.paper_search.crossref import CrossrefSearcher
from src.paper_search.pubmed import PubMedSearcher
from src.paper_search.europe_pmc import EuropePMCSearcher

# 聚合器
from src.paper_search.aggregator import SearchAggregator

# RSS 监控
from src.paper_search.rss_watcher import fetch_rss_papers, run_rss_watch

# 期刊监控清单
from src.paper_search.journal_watchlist import JournalWatchlist

__all__ = [
    # 数据模型
    "PaperMetadata",
    "SearchQuery",
    "SearchResult",
    # 检索器
    "PaperSearcher",
    # 抽象基类
    "BaseSearcher",
    # 检索源
    "OpenAlexSearcher",
    "CrossrefSearcher",
    "PubMedSearcher",
    "EuropePMCSearcher",
    # 聚合器
    "SearchAggregator",
    # RSS
    "fetch_rss_papers",
    "run_rss_watch",
    # 期刊清单
    "JournalWatchlist",
]
