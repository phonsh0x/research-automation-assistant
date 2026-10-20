"""
OpenAlex 检索源 — 调用 OpenAlex REST API 进行文献检索。

API 文档: https://docs.openalex.org/api-entities/works
速率限制: 每秒最多 10 次请求。
"""

import time
import requests
from typing import Optional

from src.paper_search.base import BaseSearcher
from src.paper_search.models import PaperMetadata, SearchQuery
from src.utils.logger import get_logger

logger = get_logger(__name__)

# API 配置
OPENALEX_BASE_URL = "https://api.openalex.org/works"
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RATE_LIMIT_DELAY = 0.11  # 每秒约 9 次请求（留出安全余量）


class OpenAlexSearcher(BaseSearcher):
    """OpenAlex API 检索源。"""

    @property
    def source_name(self) -> str:
        return "openalex"

    def search(self, query: SearchQuery) -> list[PaperMetadata]:
        """
        通过 OpenAlex API 执行文献检索。

        Args:
            query: 检索查询参数

        Returns:
            标准化 PaperMetadata 列表
        """
        logger.info(f"OpenAlex 检索开始: keywords='{query.keywords}', max={query.max_results}")

        params = {
            "search": query.keywords,
            "per_page": min(query.max_results, 200),
            "sort": self._map_sort(query.sort_by),
        }

        # 年份过滤
        if query.year_from or query.year_to:
            year_filter = self._build_year_filter(query.year_from, query.year_to)
            if year_filter:
                params["filter"] = year_filter

        # OA 过滤
        if query.filter_oa_only:
            oa_filter = "is_oa:true"
            if "filter" in params:
                params["filter"] += "," + oa_filter
            else:
                params["filter"] = oa_filter

        papers = []
        page_count = 0

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = requests.get(
                    OPENALEX_BASE_URL,
                    params=params,
                    timeout=REQUEST_TIMEOUT,
                    headers={"User-Agent": "ResearchAutomationAssistant/0.1.0"},
                )
                response.raise_for_status()
                data = response.json()
                page_count += 1

                works = data.get("results", [])
                for work in works:
                    paper = self._parse_work(work)
                    if paper is not None:
                        papers.append(paper)

                logger.info(f"OpenAlex 检索成功: 获取 {len(works)} 条结果（第 {page_count} 页）")
                break

            except requests.exceptions.Timeout as e:
                logger.warning(f"OpenAlex 请求超时 (尝试 {attempt}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"OpenAlex 请求最终失败: {e}")

            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    retry_after = self._get_retry_after(e.response)
                    logger.warning(f"OpenAlex 速率限制 (429)，等待 {retry_after} 秒...")
                    time.sleep(retry_after)
                elif attempt < MAX_RETRIES:
                    logger.warning(f"OpenAlex HTTP 错误 (尝试 {attempt}/{MAX_RETRIES}): {e}")
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"OpenAlex HTTP 错误最终失败: {e}")
                    break

            except requests.exceptions.RequestException as e:
                logger.warning(f"OpenAlex 请求异常 (尝试 {attempt}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"OpenAlex 请求最终失败: {e}")

            time.sleep(RATE_LIMIT_DELAY)

        logger.info(f"OpenAlex 检索完成: 共 {len(papers)} 条结果")
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
        logger.info(f"OpenAlex 查期刊: journal='{journal_name}', days={days}")

        from datetime import datetime, timedelta
        since_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

        params = {
            "filter": f"primary_location.source.display_name.search:{journal_name},from_publication_date:{since_date}",
            "sort": "publication_date:desc",
            "per_page": 200,
        }

        papers = []

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = requests.get(
                    OPENALEX_BASE_URL,
                    params=params,
                    timeout=REQUEST_TIMEOUT,
                    headers={"User-Agent": "ResearchAutomationAssistant/0.1.0"},
                )
                response.raise_for_status()
                data = response.json()

                for work in data.get("results", []):
                    paper = self._parse_work(work)
                    if paper is not None:
                        papers.append(paper)

                logger.info(f"OpenAlex 期刊检索: 获取 {len(papers)} 条结果")
                break

            except requests.exceptions.RequestException as e:
                logger.warning(f"OpenAlex 期刊检索异常 (尝试 {attempt}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"OpenAlex 期刊检索最终失败: {e}")

            time.sleep(RATE_LIMIT_DELAY)

        return papers

    def resolve_doi(self, doi: str) -> Optional[PaperMetadata]:
        """
        通过 DOI 从 OpenAlex 获取单篇论文元数据。

        Args:
            doi: 论文 DOI

        Returns:
            PaperMetadata，失败返回 None
        """
        logger.info(f"OpenAlex DOI 解析: {doi}")
        url = f"https://api.openalex.org/works/doi:{doi}"

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = requests.get(
                    url,
                    timeout=REQUEST_TIMEOUT,
                    headers={"User-Agent": "ResearchAutomationAssistant/0.1.0"},
                )
                if response.status_code == 404:
                    logger.warning(f"OpenAlex DOI 未找到: {doi}")
                    return None
                response.raise_for_status()
                work = response.json()
                return self._parse_work(work)
            except requests.exceptions.RequestException as e:
                logger.warning(f"OpenAlex DOI 查询异常 (尝试 {attempt}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"OpenAlex DOI 查询最终失败: {e}")
                    return None
            time.sleep(RATE_LIMIT_DELAY)

        return None

    # ==========================================================================
    # 私有方法
    # ==========================================================================

    @staticmethod
    def _map_sort(sort_by: str) -> str:
        """映射排序方式到 OpenAlex 参数。"""
        mapping = {
            "relevance": "relevance_score:desc",
            "year": "publication_date:desc",
            "citations": "cited_by_count:desc",
        }
        return mapping.get(sort_by, "relevance_score:desc")

    @staticmethod
    def _build_year_filter(year_from: Optional[int], year_to: Optional[int]) -> str:
        """构建 OpenAlex 年份过滤条件。

        OpenAlex 的 ``filter`` 参数以逗号分隔，语义是 **AND**，因此不能重复拼接
        两个 ``publication_year``（那会变成"等于 2020 且等于 2025"，结果恒为空）。
        年份区间必须使用官方的 ``from_publication_date`` / ``to_publication_date``
        便捷过滤器，与 ``journal_watchlist`` 等处的既有用法保持一致。
        """
        filters = []
        if year_from:
            filters.append(f"from_publication_date:{year_from}-01-01")
        if year_to:
            filters.append(f"to_publication_date:{year_to}-12-31")
        return ",".join(filters)

    @staticmethod
    def _get_retry_after(response) -> int:
        """从响应头中读取 Retry-After 值。"""
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return int(retry_after)
            except ValueError:
                pass
        return 5  # 默认等待 5 秒

    @staticmethod
    def _parse_work(work: dict) -> Optional[PaperMetadata]:
        """将 OpenAlex work 对象转换为 PaperMetadata。"""
        try:
            # 基础信息
            doi = None
            doi_url = work.get("doi")
            if doi_url and isinstance(doi_url, str):
                doi = doi_url.replace("https://doi.org/", "")

            pmid = None
            ids = work.get("ids", {})
            pmid_raw = ids.get("pmid")
            if pmid_raw:
                pmid = str(pmid_raw).split("/")[-1]

            pmcid = None
            pmcid_raw = ids.get("pmcid")
            if pmcid_raw:
                pmcid = pmcid_raw

            # 标题
            title = work.get("title", "未知标题")

            # 作者
            authors = []
            for authorship in work.get("authorships", []):
                author_data = authorship.get("author", {})
                name = author_data.get("display_name", "")
                if name:
                    authors.append(name)

            # 年份
            year = work.get("publication_year")

            # 期刊
            primary_location = work.get("primary_location", {}) or {}
            source = primary_location.get("source", {}) or {}
            journal = source.get("display_name")

            # 摘要
            abstract = None
            abstract_inverted = work.get("abstract_inverted_index")
            if abstract_inverted and isinstance(abstract_inverted, dict):
                try:
                    # 重建摘要文本
                    word_positions = {}
                    for word, positions in abstract_inverted.items():
                        for pos in positions:
                            word_positions[pos] = word
                    abstract = " ".join(word_positions[k] for k in sorted(word_positions))
                except Exception:
                    pass

            # 关键词
            keywords = []
            for concept in work.get("concepts", []):
                name = concept.get("display_name", "")
                if name and concept.get("level", 0) == 0:
                    keywords.append(name)

            # OA 状态
            oa_info = work.get("open_access", {})
            oa_status_map = {
                "gold": "gold",
                "green": "green",
                "hybrid": "hybrid",
                "bronze": "bronze",
            }
            oa_status = oa_status_map.get(oa_info.get("oa_status", ""), "unknown")
            oa_url = oa_info.get("oa_url")

            # 引用次数
            citation_count = work.get("cited_by_count", 0) or 0

            # 宗卷/期/页码
            biblio = work.get("biblio", {}) or {}
            volume = biblio.get("volume")
            issue = biblio.get("issue")

            # 页码从 biblio 获取
            first_page = biblio.get("first_page")
            last_page = biblio.get("last_page")
            pages = None
            if first_page and last_page:
                pages = f"{first_page}-{last_page}"
            elif first_page:
                pages = str(first_page)

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
                source_api="openalex",
                source_id=work.get("id", "").replace("https://openalex.org/", ""),
                oa_status=oa_status,
                oa_url=oa_url,
            )
        except Exception as e:
            logger.error(f"解析 OpenAlex work 失败: {e}")
            return None
