"""
PubMed 检索源 — 调用 NCBI Entrez E-utilities API 进行文献检索。

API 文档: https://www.ncbi.nlm.nih.gov/books/NBK25501/
速率限制: 每秒最多 3 次请求（无 API Key 情况下）。
"""

import time
import requests
from typing import Optional

from src.paper_search.base import BaseSearcher
from src.paper_search.models import PaperMetadata, SearchQuery
from src.utils.logger import get_logger

logger = get_logger(__name__)

# API 配置
PUBMED_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RATE_LIMIT_DELAY = 0.34  # 每秒最多 3 次请求


class PubMedSearcher(BaseSearcher):
    """PubMed Entrez API 检索源。"""

    @property
    def source_name(self) -> str:
        return "pubmed"

    def search(self, query: SearchQuery) -> list[PaperMetadata]:
        """
        通过 PubMed E-utilities 执行文献检索（两步流程：esearch + efetch）。

        Args:
            query: 检索查询参数

        Returns:
            标准化 PaperMetadata 列表
        """
        logger.info(f"PubMed 检索开始: keywords='{query.keywords}', max={query.max_results}")

        # 第一步：esearch 获取 PMID 列表
        pmids = self._esearch(query)
        if not pmids:
            logger.warning("PubMed esearch 未找到匹配结果。")
            return []

        logger.info(f"PubMed esearch 获取 {len(pmids)} 个 PMID")

        # 第二步：efetch 获取详细元数据
        papers = self._efetch(pmids[: query.max_results])

        logger.info(f"PubMed 检索完成: 共 {len(papers)} 条结果")
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
        logger.info(f"PubMed 查期刊: journal='{journal_name}', days={days}")

        from datetime import datetime, timedelta
        from_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y/%m/%d")

        # 构造 PubMed 查询：期刊名 + 日期范围
        query_str = f'"{journal_name}"[Journal] AND ("{from_date}"[Date - Publication] : "3000"[Date - Publication])'

        search_query = SearchQuery(
            keywords=query_str,
            max_results=100,
            sources=["pubmed"],
        )

        return self.search(search_query)

    def resolve_doi(self, doi: str) -> Optional[PaperMetadata]:
        """
        通过 DOI 从 PubMed 获取单篇论文元数据。

        Args:
            doi: 论文 DOI

        Returns:
            PaperMetadata，失败返回 None
        """
        logger.info(f"PubMed DOI 解析: {doi}")
        query = SearchQuery(keywords=f"{doi}[DOI]", max_results=1, sources=["pubmed"])
        papers = self.search(query)
        return papers[0] if papers else None

    # ==========================================================================
    # 私有方法
    # ==========================================================================

    def _esearch(self, query: SearchQuery) -> list[str]:
        """
        ESearch: 根据查询获取 PMID 列表。

        Returns:
            PMID 字符串列表
        """
        params = {
            "db": "pubmed",
            "term": query.keywords,
            "retmax": min(query.max_results, 200),
            "retmode": "json",
            "sort": self._map_sort(query.sort_by),
        }

        # 年份过滤
        if query.year_from or query.year_to:
            if query.year_from:
                params["mindate"] = str(query.year_from)
            if query.year_to:
                params["maxdate"] = str(query.year_to)
            params["datetype"] = "pdat"

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = requests.get(
                    PUBMED_ESEARCH_URL,
                    params=params,
                    timeout=REQUEST_TIMEOUT,
                )
                response.raise_for_status()
                data = response.json()
                id_list = data.get("esearchresult", {}).get("idlist", [])
                time.sleep(RATE_LIMIT_DELAY)
                return id_list

            except requests.exceptions.Timeout as e:
                logger.warning(f"PubMed esearch 超时 (尝试 {attempt}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** attempt)

            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    retry_after = self._get_retry_after(e.response)
                    logger.warning(f"PubMed 速率限制 (429)，等待 {retry_after} 秒...")
                    time.sleep(retry_after)
                elif attempt < MAX_RETRIES:
                    logger.warning(f"PubMed HTTP 错误 (尝试 {attempt}/{MAX_RETRIES}): {e}")
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"PubMed esearch 最终失败: {e}")
                    return []

            except requests.exceptions.RequestException as e:
                logger.warning(f"PubMed esearch 异常 (尝试 {attempt}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"PubMed esearch 最终失败: {e}")
                    return []

        return []

    def _efetch(self, pmids: list[str]) -> list[PaperMetadata]:
        """
        EFetch: 根据 PMID 列表获取详细的论文元数据。

        Args:
            pmids: PMID 字符串列表

        Returns:
            标准化 PaperMetadata 列表
        """
        if not pmids:
            return []

        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
        }

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = requests.get(
                    PUBMED_EFETCH_URL,
                    params=params,
                    timeout=REQUEST_TIMEOUT,
                )
                response.raise_for_status()
                time.sleep(RATE_LIMIT_DELAY)
                return self._parse_efetch_xml(response.text)

            except requests.exceptions.RequestException as e:
                logger.warning(f"PubMed efetch 异常 (尝试 {attempt}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"PubMed efetch 最终失败: {e}")
                    return []

        return []

    @staticmethod
    def _parse_efetch_xml(xml_text: str) -> list[PaperMetadata]:
        """解析 PubMed efetch XML 响应，提取论文元数据。"""
        import xml.etree.ElementTree as ET

        papers = []
        try:
            root = ET.fromstring(xml_text)
            for article_elem in root.findall(".//PubmedArticle"):
                paper = PubMedSearcher._parse_pubmed_article(article_elem)
                if paper is not None:
                    papers.append(paper)
        except ET.ParseError as e:
            logger.error(f"解析 PubMed XML 失败: {e}")

        return papers

    @staticmethod
    def _parse_pubmed_article(article_elem) -> Optional[PaperMetadata]:
        """解析单个 PubmedArticle XML 元素。"""
        try:
            # PMID
            pmid_elem = article_elem.find(".//PMID")
            pmid = pmid_elem.text if pmid_elem is not None else None

            # 文章引用
            citation = article_elem.find(".//Article")
            if citation is None:
                return None

            # 标题
            title_elem = citation.find(".//ArticleTitle")
            title = title_elem.text if title_elem is not None else "未知标题"

            # 摘要
            abstract_parts = []
            abstract_elem = citation.find(".//Abstract")
            if abstract_elem is not None:
                for abs_text in abstract_elem.findall(".//AbstractText"):
                    label = abs_text.get("Label", "")
                    text = abs_text.text or ""
                    if label:
                        abstract_parts.append(f"{label}: {text}")
                    else:
                        abstract_parts.append(text)
            abstract = " ".join(abstract_parts) if abstract_parts else None

            # 作者
            authors = []
            author_list = citation.find(".//AuthorList")
            if author_list is not None:
                for author in author_list.findall(".//Author"):
                    last = author.findtext("LastName") or ""
                    fore = author.findtext("ForeName") or ""
                    name = f"{fore} {last}".strip()
                    if name:
                        authors.append(name)

            # 期刊
            journal_elem = citation.find(".//Journal")
            journal = None
            issn = None
            volume = None
            issue = None
            pages = None
            year = None

            if journal_elem is not None:
                journal_title = journal_elem.find(".//Title")
                journal = journal_title.text if journal_title is not None else None

                issn_elem = journal_elem.find(".//ISSN")
                issn = issn_elem.text if issn_elem is not None else None

                journal_issue = journal_elem.find(".//JournalIssue")
                if journal_issue is not None:
                    vol_elem = journal_issue.find(".//Volume")
                    volume = vol_elem.text if vol_elem is not None else None

                    iss_elem = journal_issue.find(".//Issue")
                    issue = iss_elem.text if iss_elem is not None else None

                    pub_date = journal_issue.find(".//PubDate")
                    if pub_date is not None:
                        yr = pub_date.findtext("Year")
                        if yr:
                            year = int(yr)

            # 页码
            page_elem = citation.find(".//Pagination")
            if page_elem is not None:
                medline_pgn = page_elem.findtext("MedlinePgn")
                if medline_pgn:
                    pages = medline_pgn

            # DOI 和其他 ID
            doi = None
            pmcid = None
            article_ids = article_elem.findall(".//ArticleId")
            for aid in article_ids:
                id_type = aid.get("IdType", "")
                if id_type == "doi":
                    doi = aid.text
                elif id_type == "pmc":
                    pmcid = aid.text

            # 关键词
            keywords = []
            kw_list = citation.find(".//KeywordList")
            if kw_list is not None:
                for kw in kw_list.findall(".//Keyword"):
                    if kw.text:
                        keywords.append(kw.text)

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
                source_api="pubmed",
                source_id=pmid,
                oa_status="unknown",
            )
        except Exception as e:
            logger.error(f"解析 PubMed 文章失败: {e}")
            return None

    @staticmethod
    def _map_sort(sort_by: str) -> str:
        """映射排序方式到 PubMed esearch 参数。"""
        mapping = {
            "relevance": "relevance",
            "year": "pub+date",
            "citations": None,  # PubMed 不支持按引用数排序
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
