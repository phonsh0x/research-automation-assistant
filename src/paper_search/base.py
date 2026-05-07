"""
检索源抽象基类 — 所有文献检索 API 客户端必须实现的统一接口。

定义 search() 和 get_recent() 两个核心方法，以及可选的 resolve_doi()。
"""

from abc import ABC, abstractmethod
from typing import Optional

from src.paper_search.models import PaperMetadata, SearchQuery
from src.utils.logger import get_logger

logger = get_logger(__name__)


class BaseSearcher(ABC):
    """检索源抽象基类，所有检索源必须实现此接口。"""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """检索源名称，如 'openalex', 'crossref'。"""
        ...

    @abstractmethod
    def search(self, query: SearchQuery) -> list[PaperMetadata]:
        """按关键词检索，返回标准化 PaperMetadata 列表。"""
        ...

    @abstractmethod
    def get_recent(self, journal_name: str, days: int = 7) -> list[PaperMetadata]:
        """获取指定期刊最近 N 天的新论文。"""
        ...

    def resolve_doi(self, doi: str) -> Optional[PaperMetadata]:
        """通过 DOI 获取单篇元数据（可选覆盖）。"""
        return None
