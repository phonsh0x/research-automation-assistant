"""
文献检索器 — 负责调用外部 API 并返回标准化结果。

Phase 1 实现概要：
  - PaperSearcher 是检索模块的主入口
  - 后续 Phase 将实现具体的 API 调用逻辑（OpenAlex、Crossref 等）
  - 目前提供接口定义和基础框架
"""

from dataclasses import dataclass, field
from typing import Optional

from src.paper_search.models import PaperMetadata, SearchQuery
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SearchResult:
    """单次检索的结果容器。"""
    query: SearchQuery                           # 原始查询
    total_count: int = 0                         # 总命中数（来自 API 的 total）
    papers: list[PaperMetadata] = field(default_factory=list)  # 当前页的结果列表
    page: int = 1                                # 当前页码
    errors: list[str] = field(default_factory=list)  # 检索过程中的错误信息


class PaperSearcher:
    """
    文献检索器 — 按关键词检索学术文献。

    支持多个合法 API 源的联合检索和去重。
    所有 API 调用均遵守速率限制，并带有超时和重试逻辑。

    Usage:
        searcher = PaperSearcher()
        query = SearchQuery(keywords="deep learning medical imaging")
        result = searcher.search(query)
        for paper in result.papers:
            print(paper.title)
    """

    def __init__(self):
        """初始化检索器，加载 API 配置。"""
        # Phase 1: 框架占位，后续实现 API 客户端初始化
        self._timeout = 30
        self._max_retries = 3
        logger.info("PaperSearcher 已初始化（Phase 1 框架）。")

    def search(self, query: SearchQuery) -> SearchResult:
        """
        执行文献检索。

        Args:
            query: 检索查询参数

        Returns:
            检索结果容器，包含标准化元数据列表
        """
        logger.info(f"检索开始: keywords='{query.keywords}', sources={query.sources}")

        result = SearchResult(query=query)

        # Phase 1 占位：返回空结果
        # 后续 Phase 将实现实际的 API 调用逻辑
        logger.warning("检索功能尚未实现（Phase 1 框架占位），返回空结果。")

        return result

    def resolve_doi(self, doi: str) -> Optional[PaperMetadata]:
        """
        通过 DOI 解析单篇论文的元数据。

        Args:
            doi: 论文 DOI

        Returns:
            论文元数据，解析失败返回 None
        """
        logger.info(f"DOI 解析: {doi}")
        # Phase 1 占位
        logger.warning("DOI 解析功能尚未实现（Phase 1 框架占位）。")
        return None

    def check_oa_status(self, doi: str) -> str:
        """
        查询论文的开放获取状态（通过 Unpaywall API）。

        Args:
            doi: 论文 DOI

        Returns:
            OA 状态：gold/green/hybrid/bronze/closed
        """
        logger.debug(f"查询 OA 状态: {doi}")
        # Phase 1 占位
        logger.warning("Unpaywall 查询功能尚未实现（Phase 1 框架占位）。")
        return "unknown"
