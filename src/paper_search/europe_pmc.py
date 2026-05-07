"""
Europe PMC 检索源 — 调用 Europe PMC REST API 进行文献检索。

API 文档: https://europepmc.org/RestfulWebService
速率限制: 每秒最多 5 次请求。
"""

import time
import requests
from typing import Optional

from src.paper_search.base import BaseSearcher
from src.paper_search.models import PaperMetadata, SearchQuery
from src.utils.logger import get_logger

logger = get_logger(__name__)

# API 配置
EUROPE_PMC_SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RATE_LIMIT_DELAY = 0.25  # 每秒最多约 4 次请求


class EuropePMCSearcher(BaseSearcher):
    """Europe PMC API 检索源。"""

    @property
    def source_name(self) -> str:
        return "europe_pmc"

    def search(self, query: SearchQuery) -> list[PaperMetadata]:
        """
        通过 Europe PMC REST API 执行文献检索。

        Args:
            query: 检索查询参数

        Returns:
            标准化 PaperMetadata 列表
        """
        logger.info(f"Europe PMC 检索开始: keywords='{query.keywords}', max={query.max_results}")

        params = {
            "query": query.keywords,
            "resultType": "core",
            "pageSize": min(query.max_results, 100),
            "format": "json",
            "sort": self._map_sort(query.sort_by),
        }

        # 年份过滤
        if query.year_from or query.year_to:
            if query.year_from:
                params["fromSearchDate"] = f"{query.year_from}-01-01"
            if query.year_to:
                params["toSearchDate"] = f"{query.year_to}-12-31"

        # OA 过滤
        if query.filter_oa_only:
            params["query"] = f"(OPEN_ACCESS:y) AND ({params['query']})"

        papers = []
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = requests.get(
                    EUROPE_PMC_SEARCH_URL,
                    params=params,
                    timeout=REQUEST_TIMEOUT,
                    headers={"User-Agent": "ResearchAutomationAssistant/0.1.0"},
                )
                response.raise_for_status()
                data = response.json()

                results = data.get("resultList", {}).get("result", [])
                for item in results:
                    paper = self._parse_result(item)
                    if paper is not None:
                        papers.append(paper)

                logger.info(f"Europe PMC 检索成功: 获取 {len(results)} 条结果")
                break

            except requests.exceptions.Timeout as e:
                logger.warning(f"Europe PMC 请求超时 (尝试 {attempt}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"Europe PMC 请求最终失败: {e}")

            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    retry_after = self._get_retry_after(e.response)
                    logger.warning(f"Europe PMC 速率限制 (429)，等待 {retry_after} 秒...")
                    time.sleep(retry_after)
                elif attempt < MAX_RETRIES:
                    logger.warning(f"Europe PMC HTTP 错误 (尝试 {attempt}/{MAX_RETRIES}): {e}")
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"Europe PMC HTTP 错误最终失败: {e}")
                    break

            except requests.exceptions.RequestException as e:
                logger.warning(f"Europe PMC 请求异常 (尝试 {attempt}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"Europe PMC 请求最终失败: {e}")

            time.sleep(RATE_LIMIT_DELAY)

        logger.info(f"Europe PMC 检索完成: 共 {len(papers)} 条结果")
        return papers

    def get_recent(self, journal_name: str, days: int = 7) -> list[PaperMetadata]:
        """
        获取指定期刊最近 N 天的新论文。

        Args:
            journal_name: 期刊名称
            days: 最近天数

        Returns:
            标准化 PaperMetadata 列表
        """
        logger.info(f"Europe PMC 查期刊: journal='{journal_name}', days={days}")

        from datetime import datetime, timedelta
        from_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

        query_str = f'(JOURNAL:"{journal_name}") AND (FIRST_PDATE:[{from_date} TO 3000-12-31])'

        search_query = SearchQuery(
            keywords=query_str,
            max_results=100,
            sources=["europe_pmc"],
        )

        return self.search(search_query)

    def resolve_doi(self, doi: str) -> Optional[PaperMetadata]:
        """
        通过 DOI 从 Europe PMC 获取单篇论文元数据。

        Args:
            doi: 论文 DOI

        Returns:
            PaperMetadata，失败返回 None
        """
        logger.info(f"Europe PMC DOI 解析: {doi}")
        query = SearchQuery(keywords=f'DOI:"{doi}"', max_results=1, sources=["europe_pmc"])
        papers = self.search(query)
        return papers[0] if papers else None

    # ==========================================================================
    # 私有方法
    # ==========================================================================

    @staticmethod
    def _map_sort(sort_by: str) -> str:
        """映射排序方式到 Europe PMC 参数。"""
        mapping = {
            "relevance": "RELEVANCE",
            "year": "P_PDATE_D",
            "citations": "CITED",
        }
        return mapping.get(sort_by, "RELEVANCE")

    @staticmethod
    def _get_retry_after(response) -> int:
        """从响应头中读取 Retry-After 值。"""
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return int(retry_after)
            except ValueError:
                pass
        return 5

    @staticmethod
    def _parse_result(item: dict) -> Optional[PaperMetadata]:
        """将 Europe PMC 检索结果转换为 PaperMetadata。"""
        try:
            # DOI
            doi = item.get("doi")

            # PMID / PMCID
            pmid = item.get("pmid")
            pmcid = item.get("pmcid")

            # 标题
            title = item.get("title", "未知标题")

            # 作者
            author_string = item.get("authorString", "")
            authors = [a.strip() for a in author_string.split(",") if a.strip()] if author_string else []

            # 年份
            pub_year = item.get("pubYear")
            year = int(pub_year) if pub_year else None

            # 期刊
            journal_info = item.get("journalInfo", {}) or {}
            if isinstance(journal_info, dict):
                journal = journal_info.get("journal", {}).get("title") if isinstance(journal_info.get("journal"), dict) else journal_info.get("journal")
            else:
                journal = item.get("journalTitle")

            # 摘要
            abstract = item.get("abstractText")

            # 卷/期/页码
            volume = journal_info.get("volume") if isinstance(journal_info, dict) and journal_info.get("volume") else None
            issue = journal_info.get("issue") if isinstance(journal_info, dict) and journal_info.get("issue") else None
            pages = journal_info.get("pages") if isinstance(journal_info, dict) and journal_info.get("pages") else None

            # 引用次数
            cited_by = item.get("citedByCount", 0) or 0
            citation_count = int(cited_by) if cited_by else 0

            # OA 状态
            oa_status = "unknown"
            if item.get("isOpenAccess") == "Y":
                oa_status = "gold"  # Europe PMC 默认识别为 gold OA

            # 关键词
            keywords = []
            mesh_list = item.get("meshHeadingList", {}) or {}
            if isinstance(mesh_list, dict):
                for mesh in mesh_list.get("meshHeading", []):
                    desc = mesh.get("descriptorName", "")
                    if desc:
                        keywords.append(desc)

            # 来源 ID
            source_id = item.get("id")

            return PaperMetadata(
                title=title,
                authors=authors,
                doi=doi,
                pmid=pmid,
                pmcid=pmcid,
                year=year,
                journal=journal,
                volume=volume,
                issue=issue,
                pages=pages,
                abstract=abstract,
                keywords=keywords,
                citation_count=citation_count,
                source_api="europe_pmc",
                source_id=source_id,
                oa_status=oa_status,
            )
        except Exception as e:
            logger.error(f"解析 Europe PMC 结果失败: {e}")
            return None
