"""
多源检索聚合器 — 协调多个检索源、去重、入库。

支持两种检索模式：
  - daily_watch: 优先 Crossref/PubMed/Europe PMC/RSS（日常监控）
  - backfill: 优先 OpenAlex（批量回填）
"""

import time
from typing import Optional

from src.paper_search.base import BaseSearcher
from src.paper_search.models import PaperMetadata, SearchQuery
from src.paper_search.searcher import SearchResult
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SearchAggregator:
    """
    多源检索聚合器。

    职责：
      - 协调多个检索源的检索请求
      - 按 DOI / (title + year) 去重
      - 将结果写入数据库
      - 记录检索运行日志

    Usage:
        searchers = [OpenAlexSearcher(), CrossrefSearcher()]
        repo = PaperRepository()
        aggregator = SearchAggregator(searchers, repo)
        result = aggregator.search(query, mode="backfill")
    """

    def __init__(self, searchers: list[BaseSearcher], repository=None):
        """
        初始化聚合器。

        Args:
            searchers: 检索源实例列表
            repository: PaperRepository 实例（可选，用于入库）
        """
        self.searchers = searchers
        self.repository = repository
        logger.info(f"SearchAggregator 已初始化，共 {len(searchers)} 个检索源。")

    def search(self, query: SearchQuery, mode: str = "backfill") -> SearchResult:
        """
        执行多源检索。

        Args:
            query: 检索查询参数
            mode: 检索模式
                  'daily_watch' — 优先 RSS/Crossref/PubMed/Europe PMC
                  'backfill' — 优先 OpenAlex

        Returns:
            SearchResult 结果容器
        """
        logger.info(f"聚合检索开始: mode='{mode}', keywords='{query.keywords}', sources={query.sources}")

        result = SearchResult(query=query)

        # 根据模式排序检索源
        ordered_searchers = self._order_searchers(mode, query.sources)

        all_papers = []
        errors = []

        for searcher in ordered_searchers:
            if query.sources and searcher.source_name not in query.sources:
                continue

            try:
                source_papers = searcher.search(query)
                all_papers.extend(source_papers)
                logger.info(f"检索源 {searcher.source_name}: 获取 {len(source_papers)} 条")
            except Exception as e:
                error_msg = f"检索源 {searcher.source_name} 失败: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        # 去重
        deduped = self.deduplicate(all_papers)
        logger.info(f"去重前: {len(all_papers)} 条, 去重后: {len(deduped)} 条")

        # 截断到最大结果数
        result.papers = deduped[: query.max_results]
        result.total_count = len(deduped)
        result.errors = errors

        logger.info(f"聚合检索完成: 最终 {len(result.papers)} 条结果")
        return result

    def deduplicate(self, papers: list[PaperMetadata]) -> list[PaperMetadata]:
        """
        按 DOI 去重；DOI 缺失时按 (title_normalized, year) 弱去重。

        合并时字段取非空值的并集，保留数据最完整的版本。

        Args:
            papers: 待去重的论文元数据列表

        Returns:
            去重后的论文列表
        """
        if not papers:
            return []

        # 第一阶段：按 DOI 去重
        doi_map: dict[str, PaperMetadata] = {}
        title_year_map: dict[str, PaperMetadata] = {}
        no_doi_papers: list[PaperMetadata] = []

        for paper in papers:
            if paper.doi:
                existing = doi_map.get(paper.doi)
                if existing:
                    doi_map[paper.doi] = self._merge_papers(existing, paper)
                else:
                    doi_map[paper.doi] = paper
            else:
                no_doi_papers.append(paper)

        # 第二阶段：对无 DOI 的论文按 title + year 弱去重
        for paper in no_doi_papers:
            key = self._make_title_year_key(paper)
            if key:
                existing = title_year_map.get(key)
                if existing:
                    title_year_map[key] = self._merge_papers(existing, paper)
                else:
                    title_year_map[key] = paper
            else:
                # 既无 DOI 也无 title+year —— 保留原样
                title_year_map[f"__unknown_{id(paper)}"] = paper

        # 合并结果
        result = list(doi_map.values()) + list(title_year_map.values())
        return result

    def save_results(self, papers: list[PaperMetadata]) -> dict:
        """
        将检索结果写入 SQLite，返回入库统计信息。

        Args:
            papers: 待入库的论文元数据列表

        Returns:
            入库统计: {new_count, updated_count, duplicate_count, failed_count, failed_details}
        """
        stats = {
            "new_count": 0,
            "updated_count": 0,
            "duplicate_count": 0,
            "failed_count": 0,
            "failed_details": [],  # [(title, doi, reason), ...]
        }

        if not self.repository:
            logger.warning("未设置 PaperRepository，跳过入库。")
            return stats

        for paper in papers:
            try:
                paper_id, action = self.repository.upsert_paper(paper)
                if action == "inserted":
                    stats["new_count"] += 1
                elif action == "updated":
                    stats["updated_count"] += 1
                else:
                    stats["duplicate_count"] += 1
            except Exception as e:
                title_short = (paper.title or "无标题")[:80]
                doi = paper.doi or "无DOI"
                logger.error(f"入库论文失败: title='{title_short}', doi={doi}, 原因={e}")
                stats["failed_count"] += 1
                stats["failed_details"].append({
                    "title": title_short,
                    "doi": doi,
                    "source": paper.source_api,
                    "reason": str(e)[:200],
                })

        logger.info(
            f"入库完成: 新增 {stats['new_count']}、更新 {stats['updated_count']}、"
            f"重复 {stats['duplicate_count']}、失败 {stats['failed_count']}"
        )
        return stats

    def record_search_run(
        self,
        run_type: str,
        sources: list[str],
        keywords: str,
        total_found: int,
        new_added: int,
        updated_count: int = 0,
        duplicate_count: int = 0,
        failed_count: int = 0,
        errors: Optional[list[str]] = None,
    ) -> None:
        """
        记录检索运行到数据库。

        Args:
            run_type: 检索类型（daily_watch / backfill）
            sources: 使用的检索源列表
            keywords: 检索关键词
            total_found: 总命中数
            new_added: 新增入库数
            updated_count: 更新数
            duplicate_count: 重复数
            failed_count: 失败数
            errors: 错误信息列表
        """
        if not self.repository:
            logger.warning("未设置 PaperRepository，跳过记录运行。")
            return

        try:
            self.repository.record_search_run(
                run_type=run_type,
                sources=sources,
                keywords=keywords,
                total_found=total_found,
                new_added=new_added,
                updated_count=updated_count,
                duplicate_count=duplicate_count,
                failed_count=failed_count,
                errors=errors,
            )
        except Exception as e:
            logger.error(f"记录检索运行失败: {e}")

    # ==========================================================================
    # 私有方法
    # ==========================================================================

    def _order_searchers(self, mode: str, sources: list[str]) -> list[BaseSearcher]:
        """根据检索模式排序检索源。"""
        if mode == "daily_watch":
            # 日常监控优先 Crossref / PubMed / Europe PMC
            priority = {"crossref": 1, "pubmed": 2, "europe_pmc": 3, "openalex": 4, "arxiv": 5, "semantic_scholar": 6}
        else:
            # 回填优先 OpenAlex
            priority = {"openalex": 1, "crossref": 2, "pubmed": 3, "europe_pmc": 4, "arxiv": 5, "semantic_scholar": 6}

        # 按优先级排序，忽略未知源
        ordered = sorted(self.searchers, key=lambda s: priority.get(s.source_name, 99))

        # 如果指定了 sources，只保留匹配的
        if sources:
            ordered = [s for s in ordered if s.source_name in sources]

        return ordered

    @staticmethod
    def _merge_papers(p1: PaperMetadata, p2: PaperMetadata) -> PaperMetadata:
        """
        合并两篇论文的元数据，非空字段优先保留。

        保留数据更完整（字段非空更多）的版本作为基础，再合并另一篇的非空字段。

        Args:
            p1: 论文 A
            p2: 论文 B

        Returns:
            合并后的 PaperMetadata
        """
        # 选择字段更完整的行为基础
        p1_fields = sum(1 for v in p1.to_dict().values() if v)
        p2_fields = sum(1 for v in p2.to_dict().values() if v)
        base = p1 if p1_fields >= p2_fields else p2
        other = p2 if base is p1 else p1

        # 合并非空字段
        if not base.doi and other.doi:
            base.doi = other.doi
        if not base.pmid and other.pmid:
            base.pmid = other.pmid
        if not base.pmcid and other.pmcid:
            base.pmcid = other.pmcid
        if not base.abstract and other.abstract:
            base.abstract = other.abstract
        if not base.journal and other.journal:
            base.journal = other.journal
        if not base.publisher and other.publisher:
            base.publisher = other.publisher
        if not base.volume and other.volume:
            base.volume = other.volume
        if not base.issue and other.issue:
            base.issue = other.issue
        if not base.pages and other.pages:
            base.pages = other.pages
        if not base.oa_url and other.oa_url:
            base.oa_url = other.oa_url
        if base.oa_status == "unknown" and other.oa_status != "unknown":
            base.oa_status = other.oa_status
        if base.citation_count == 0 and other.citation_count > 0:
            base.citation_count = other.citation_count

        # 合并作者列表
        if not base.authors and other.authors:
            base.authors = other.authors
        elif base.authors and other.authors and len(other.authors) > len(base.authors):
            base.authors = other.authors

        # 合并关键词
        if not base.keywords and other.keywords:
            base.keywords = other.keywords
        elif base.keywords and other.keywords:
            base_set = set(base.keywords)
            base_set.update(other.keywords)
            base.keywords = list(base_set)

        return base

    @staticmethod
    def _make_title_year_key(paper: PaperMetadata) -> Optional[str]:
        """
        生成 title + year 归一化组合键，用于弱去重。

        Args:
            paper: 论文元数据

        Returns:
            归一化键，失败返回 None
        """
        if not paper.title:
            return None

        # 标题归一化：去除标点、多余空格、转为小写
        import re
        title_norm = re.sub(r"[^\w\s]", "", paper.title.lower())
        title_norm = re.sub(r"\s+", " ", title_norm).strip()

        year = paper.year or 0
        return f"{title_norm[:100]}|{year}"
