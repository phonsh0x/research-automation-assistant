"""
文献检索器 — 负责调用外部 API 并返回标准化结果。

Phase 2.1 重构：PaperSearcher 现在是 SearchAggregator 的向后兼容包装器。
具体检索逻辑已拆分到各独立检索源模块中：
  - OpenAlexSearcher → openalex.py
  - CrossrefSearcher → crossref.py
  - PubMedSearcher → pubmed.py
  - EuropePMCSearcher → europe_pmc.py
  - SearchAggregator → aggregator.py
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
    total_count: int = 0                         # 总命中数（去重后）
    papers: list[PaperMetadata] = field(default_factory=list)  # 当前页的结果列表
    page: int = 1                                # 当前页码
    errors: list[str] = field(default_factory=list)  # 检索过程中的错误信息


class PaperSearcher:
    """
    文献检索器 — 向后兼容包装器。

    内部委托给 SearchAggregator 执行实际检索。

    Usage:
        searcher = PaperSearcher()
        query = SearchQuery(keywords="deep learning medical imaging")
        result = searcher.search(query)
        for paper in result.papers:
            print(paper.title)
    """

    def __init__(self):
        """初始化检索器，创建基础检索源。"""
        self._timeout = 30
        self._max_retries = 3

        # 惰性加载检索源和聚合器
        self._aggregator = None
        self._repository = None

        logger.info("PaperSearcher 已初始化（Phase 2.1 聚合器包装）。")

    @property
    def aggregator(self):
        """惰性初始化 SearchAggregator。"""
        if self._aggregator is None:
            from src.paper_search.aggregator import SearchAggregator
            from src.paper_search.openalex import OpenAlexSearcher
            self._aggregator = SearchAggregator(
                searchers=[OpenAlexSearcher()],
                repository=self.repository,
            )
        return self._aggregator

    @property
    def repository(self):
        """惰性初始化 PaperRepository。"""
        if self._repository is None:
            from src.storage.repository import PaperRepository
            self._repository = PaperRepository()
        return self._repository

    def _resolve_searchers(self, sources: list[str]) -> list:
        """根据 source 名称列表创建对应的检索源实例。"""
        searchers = []
        for source in sources:
            try:
                if source == "openalex":
                    from src.paper_search.openalex import OpenAlexSearcher
                    searchers.append(OpenAlexSearcher())
                elif source == "crossref":
                    from src.paper_search.crossref import CrossrefSearcher
                    searchers.append(CrossrefSearcher())
                elif source == "pubmed":
                    from src.paper_search.pubmed import PubMedSearcher
                    searchers.append(PubMedSearcher())
                elif source == "europe_pmc":
                    from src.paper_search.europe_pmc import EuropePMCSearcher
                    searchers.append(EuropePMCSearcher())
                else:
                    logger.warning(f"未知检索源: {source}，已跳过。")
            except Exception as e:
                logger.error(f"初始化检索源 {source} 失败: {e}")
        return searchers

    def search(self, query: SearchQuery) -> SearchResult:
        """
        执行文献检索。

        Args:
            query: 检索查询参数

        Returns:
            检索结果容器，包含标准化元数据列表
        """
        logger.info(f"检索开始: keywords='{query.keywords}', sources={query.sources}")

        from src.paper_search.aggregator import SearchAggregator

        searchers = self._resolve_searchers(query.sources)
        if not searchers:
            logger.warning("没有可用的检索源。")
            return SearchResult(query=query, errors=["没有可用的检索源"])

        agg = SearchAggregator(searchers=searchers, repository=self.repository)
        result = agg.search(query, mode="backfill")

        # 入库检索结果
        save_stats = agg.save_results(result.papers)

        # 记录检索运行（写入真实统计）
        agg.record_search_run(
            run_type="backfill",
            sources=query.sources,
            keywords=query.keywords,
            total_found=result.total_count,
            new_added=save_stats["new_count"],
            updated_count=save_stats["updated_count"],
            duplicate_count=save_stats["duplicate_count"],
            failed_count=save_stats["failed_count"],
            errors=result.errors + [
                f"失败: {fd['title'][:40]} ({fd['reason'][:80]})"
                for fd in save_stats["failed_details"][:5]
            ] if save_stats["failed_details"] else result.errors,
        )

        return result

    def resolve_doi(self, doi: str) -> Optional[PaperMetadata]:
        """
        通过 DOI 解析单篇论文的元数据（尝试所有源）。

        Args:
            doi: 论文 DOI

        Returns:
            论文元数据，解析失败返回 None
        """
        logger.info(f"DOI 解析: {doi}")

        resolvers = []

        try:
            from src.paper_search.openalex import OpenAlexSearcher
            resolvers.append(OpenAlexSearcher())
        except Exception:
            pass

        try:
            from src.paper_search.crossref import CrossrefSearcher
            resolvers.append(CrossrefSearcher())
        except Exception:
            pass

        for resolver in resolvers:
            paper = resolver.resolve_doi(doi)
            if paper:
                return paper

        logger.warning(f"DOI 解析失败: {doi}")
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
        # Phase 2.1: OA 状态暂由各检索源返回，不独立调用 Unpaywall
        logger.warning("Unpaywall 查询功能尚未实现，返回 unknown。")
        return "unknown"
