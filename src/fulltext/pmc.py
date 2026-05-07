"""
PMC 全文解析器 — 通过 PubMed Central (PMC) 获取开放获取 PDF。
"""

import re
import time
from typing import Optional

import requests

from src.fulltext.base import FullTextResult, FullTextResolver
from src.utils.logger import get_logger

logger = get_logger(__name__)

_PUBMED_RATE_LIMIT = 0.34
_last_request_time: float = 0.0
_PMC_PDF_BASE = "https://www.ncbi.nlm.nih.gov/pmc/articles"


class PMCResolver(FullTextResolver):
    """
    PMC 全文解析器。

    通过 PMCID 直接获取 PDF，或通过 PMID 转换获取 PMCID 后下载。
    约束: 仅处理 PMC 官方域名，遵守 NCBI E-utilities 速率限制。
    """

    @property
    def source_name(self) -> str:
        return "pmc"

    def resolve(self, paper: dict) -> FullTextResult:
        paper_id = paper.get("paper_id", paper.get("id", 0))
        doi = paper.get("doi")
        title = paper.get("title")
        pmcid = paper.get("pmcid")
        pmid = paper.get("pmid")

        # 优先使用 PMCID
        if pmcid:
            return self._build_pmc_result(paper_id, doi, title, pmcid)

        # 无 PMCID 但有 PMID，尝试转换
        if pmid:
            converted_pmcid = self._pmid_to_pmcid(pmid)
            if converted_pmcid:
                return self._build_pmc_result(paper_id, doi, title, converted_pmcid)

        return FullTextResult(
            paper_id=paper_id, doi=doi, title=title,
            source=self.source_name,
            access_status="unavailable", legal_status="unknown",
            error_message="论文无 PMCID 或 PMID，无法通过 PMC 获取",
        )

    def _build_pmc_result(
        self, paper_id: int, doi: Optional[str],
        title: Optional[str], pmcid: str,
    ) -> FullTextResult:
        pmcid_clean = pmcid.replace("PMC", "").strip() if pmcid.startswith("PMC") else pmcid
        pdf_url = f"{_PMC_PDF_BASE}/PMC{pmcid_clean}/pdf/"
        logger.info(f"PMC 构建 PDF URL: PMCID={pmcid_clean}")
        return FullTextResult(
            paper_id=paper_id, doi=doi, title=title,
            source=self.source_name,
            access_status="open_access", legal_status="legal_oa",
            pdf_url=pdf_url,
            landing_page_url=f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid_clean}/",
            risk_level="low",
        )

    def _pmid_to_pmcid(self, pmid: str) -> Optional[str]:
        """通过 NCBI E-utilities EFetch 将 PMID 转为 PMCID。"""
        global _last_request_time
        elapsed = time.time() - _last_request_time
        if elapsed < _PUBMED_RATE_LIMIT:
            time.sleep(_PUBMED_RATE_LIMIT - elapsed)

        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        params = {"db": "pmc", "id": pmid, "retmode": "xml"}
        logger.info(f"PMID 转 PMCID: PMID={pmid}")

        try:
            _last_request_time = time.time()
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            content = resp.text

            match = re.search(
                r'<article-id\s+pub-id-type="pmc"[^>]*>PMC(\d+)</article-id>',
                content, re.IGNORECASE,
            )
            if match:
                pmcid = f"PMC{match.group(1)}"
                logger.info(f"PMID {pmid} 转 PMCID 成功: {pmcid}")
                return pmcid

            match = re.search(
                r'<article-id\s+pub-id-type="pmc"[^>]*>PMC(\d+\.?\d*)</article-id>',
                content, re.IGNORECASE,
            )
            if match:
                pmcid = f"PMC{match.group(1)}"
                logger.info(f"PMID {pmid} 转 PMCID 成功(备用): {pmcid}")
                return pmcid

            logger.info(f"PMID {pmid} 无对应 PMCID")
            return None
        except Exception as e:
            logger.warning(f"PMID 转 PMCID 异常: PMID={pmid}, 原因={e}")
            return None
