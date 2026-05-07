"""
Crossref 检索源 — 调用 Crossref REST API 进行文献检索。

API 文档: https://api.crossref.org/swagger-ui/index.html
礼貌策略: 请在请求中设置 User-Agent 并包含联系邮箱。
"""

import time
import requests
from typing import Optional

from src.paper_search.base import BaseSearcher
from src.paper_search.models import PaperMetadata, SearchQuery
from src.utils.logger import get_logger

logger = get_logger(__name__)

# API 配置
CROSSREF_BASE_URL = "https://api.crossref.org/works"
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
POLITE_DELAY = 0.2  # Crossref 建议每秒不超过 5 次请求


class CrossrefSearcher(BaseSearcher):
    """Crossref API 检索源。"""

    @property
    def source_name(self) -> str:
        return "crossref"

    def search(self, query: SearchQuery) -> list[PaperMetadata]:
        """
        通过 Crossref API 执行文献检索。

        Args:
            query: 检索查询参数

        Returns:
            标准化 PaperMetadata 列表
        """
        logger.info(f"Crossref 检索开始: keywords='{query.keywords}', max={query.max_results}")

        params = {
            "query": query.keywords,
            "rows": min(query.max_results, 100),
            "sort": self._map_sort(query.sort_by),
            "order": "desc",
        }

        # 年份过滤
        if query.year_from is not None and query.year_to is not None:
            params["filter"] = f"from-pub-date:{query.year_from},until-pub-date:{query.year_to}"

        papers = []
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = requests.get(
                    CROSSREF_BASE_URL,
                    params=params,
                    timeout=REQUEST_TIMEOUT,
                    headers={"User-Agent": "ResearchAutomationAssistant/0.1.0 (mailto:research@example.com)"},
                )
                response.raise_for_status()
                data = response.json()

                items = data.get("message", {}).get("items", [])
                for item in items:
                    paper = self._parse_item(item)
                    if paper is not None:
                        papers.append(paper)

                logger.info(f"Crossref 检索成功: 获取 {len(items)} 条结果")
                break

            except requests.exceptions.Timeout as e:
                logger.warning(f"Crossref 请求超时 (尝试 {attempt}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"Crossref 请求最终失败: {e}")

            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    retry_after = self._get_retry_after(e.response)
                    logger.warning(f"Crossref 速率限制 (429)，等待 {retry_after} 秒...")
                    time.sleep(retry_after)
                elif attempt < MAX_RETRIES:
                    logger.warning(f"Crossref HTTP 错误 (尝试 {attempt}/{MAX_RETRIES}): {e}")
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"Crossref HTTP 错误最终失败: {e}")
                    break

            except requests.exceptions.RequestException as e:
                logger.warning(f"Crossref 请求异常 (尝试 {attempt}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"Crossref 请求最终失败: {e}")

            time.sleep(POLITE_DELAY)

        logger.info(f"Crossref 检索完成: 共 {len(papers)} 条结果")
        return papers

    def get_recent(self, journal_name: str, days: int = 7) -> list[PaperMetadata]:
        """
        获取指定期刊最近 N 天的新论文。

        Args:
            journal_name: 期刊名称（Crossref 查询期刊名）
            days: 最近天数

        Returns:
            标准化 PaperMetadata 列表
        """
        logger.info(f"Crossref 查期刊: journal='{journal_name}', days={days}")

        from datetime import datetime, timedelta
        from_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

        params = {
            "query": journal_name,
            "filter": f"type:journal-article,from-pub-date:{from_date}",
            "rows": 100,
            "sort": "published",
            "order": "desc",
        }

        papers = []
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = requests.get(
                    CROSSREF_BASE_URL,
                    params=params,
                    timeout=REQUEST_TIMEOUT,
                    headers={"User-Agent": "ResearchAutomationAssistant/0.1.0 (mailto:research@example.com)"},
                )
                response.raise_for_status()
                data = response.json()

                items = data.get("message", {}).get("items", [])
                for item in items:
                    paper = self._parse_item(item)
                    if paper is not None:
                        papers.append(paper)

                logger.info(f"Crossref 期刊检索: 获取 {len(items)} 条结果")
                break

            except requests.exceptions.RequestException as e:
                logger.warning(f"Crossref 期刊检索异常 (尝试 {attempt}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"Crossref 期刊检索最终失败: {e}")

            time.sleep(POLITE_DELAY)

        return papers

    def resolve_doi(self, doi: str) -> Optional[PaperMetadata]:
        """
        通过 DOI 从 Crossref 获取单篇论文元数据。

        Args:
            doi: 论文 DOI

        Returns:
            PaperMetadata，失败返回 None
        """
        logger.info(f"Crossref DOI 解析: {doi}")
        url = f"{CROSSREF_BASE_URL}/{doi}"

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = requests.get(
                    url,
                    timeout=REQUEST_TIMEOUT,
                    headers={"User-Agent": "ResearchAutomationAssistant/0.1.0 (mailto:research@example.com)"},
                )
                if response.status_code == 404:
                    logger.warning(f"Crossref DOI 未找到: {doi}")
                    return None
                response.raise_for_status()
                item = response.json().get("message", {})
                return self._parse_item(item)
            except requests.exceptions.RequestException as e:
                logger.warning(f"Crossref DOI 查询异常 (尝试 {attempt}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"Crossref DOI 查询最终失败: {e}")
                    return None
            time.sleep(POLITE_DELAY)

        return None

    # ==========================================================================
    # 私有方法
    # ==========================================================================

    @staticmethod
    def _map_sort(sort_by: str) -> str:
        """映射排序方式到 Crossref 参数。"""
        mapping = {
            "relevance": "relevance",
            "year": "published",
            "citations": None,  # Crossref 不支持按引用数排序
        }
        return mapping.get(sort_by, "relevance")

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
    def _parse_item(item: dict) -> Optional[PaperMetadata]:
        """将 Crossref API 返回的 work 对象转换为 PaperMetadata。"""
        try:
            # DOI
            doi = item.get("DOI")

            # 标题
            title_list = item.get("title", [])
            title = title_list[0] if title_list else "未知标题"

            # 作者
            authors = []
            for author_data in item.get("author", []):
                given = author_data.get("given", "")
                family = author_data.get("family", "")
                name = f"{given} {family}".strip()
                if name:
                    authors.append(name)

            # 年份
            year = None
            created = item.get("created", {})
            date_parts = created.get("date-parts", [[]])
            if date_parts and date_parts[0]:
                year = date_parts[0][0]

            published = item.get("published-print", {}) or item.get("published-online", {})
            pub_parts = published.get("date-parts", [[]])
            if pub_parts and pub_parts[0]:
                year = pub_parts[0][0]

            # 期刊
            container = item.get("container-title", [])
            journal = container[0] if container else None

            # 摘要
            abstract = item.get("abstract")

            # 关键词（Crossref 中的 subject）
            keywords = item.get("subject", [])

            # 出版社
            publisher = item.get("publisher")

            # 卷/期/页码
            volume = item.get("volume")
            issue = item.get("issue")
            page = item.get("page")

            # 引用次数
            citation_count = item.get("is-referenced-by-count", 0) or 0

            return PaperMetadata(
                title=title,
                authors=authors,
                doi=doi,
                year=year,
                journal=journal,
                volume=volume,
                issue=issue,
                pages=page,
                publisher=publisher,
                abstract=abstract,
                keywords=keywords,
                citation_count=citation_count,
                source_api="crossref",
                source_id=doi,
                oa_status="unknown",
            )
        except Exception as e:
            logger.error(f"解析 Crossref item 失败: {e}")
            return None
