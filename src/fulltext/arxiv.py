"""
arXiv 全文解析器 — 通过 arXiv 官方域名获取预印本 PDF。
"""

import re
import time
from typing import Optional

from src.fulltext.base import FullTextResult, FullTextResolver
from src.fulltext.downloader import validate_url
from src.utils.logger import get_logger

logger = get_logger(__name__)

_ARXIV_PDF_BASE = "https://arxiv.org/pdf"
_ARXIV_RATE_LIMIT = 1.0
_last_request_time: float = 0.0

_ARXIV_ID_PATTERN = re.compile(
    r"^([a-z\-]+/\d{4,}|"
    r"\d{4}\.\d{4,6})"
    r"(v\d+)?$"
)


class ArxivResolver(FullTextResolver):
    """
    arXiv 全文解析器。

    根据 arXiv ID 构建官方 PDF URL。
    支持旧格式 (hep-th/9901001) 和新格式 (1501.00001)。
    约束: 仅使用 https://arxiv.org 官方域名，遵守礼貌使用速率限制。
    """

    @property
    def source_name(self) -> str:
        return "arxiv"

    def resolve(self, paper: dict) -> FullTextResult:
        paper_id = paper.get("paper_id", paper.get("id", 0))
        doi = paper.get("doi")
        title = paper.get("title")
        arxiv_id = paper.get("arxiv_id")

        if not arxiv_id:
            return FullTextResult(
                paper_id=paper_id, doi=doi, title=title,
                source=self.source_name,
                access_status="unavailable", legal_status="unknown",
                error_message="论文无 arXiv ID",
            )

        arxiv_id = self._clean_arxiv_id(arxiv_id)
        if not arxiv_id:
            return FullTextResult(
                paper_id=paper_id, doi=doi, title=title,
                source=self.source_name,
                access_status="unavailable", legal_status="unknown",
                error_message=f"无法解析 arXiv ID 格式: {paper.get('arxiv_id')}",
            )

        pdf_url = f"{_ARXIV_PDF_BASE}/{arxiv_id}.pdf"
        landing_page_url = f"https://arxiv.org/abs/{arxiv_id}"

        if not validate_url(pdf_url):
            return FullTextResult(
                paper_id=paper_id, doi=doi, title=title,
                source=self.source_name,
                access_status="unavailable", legal_status="unknown",
                error_message=f"arXiv URL 校验失败: {pdf_url}",
            )

        global _last_request_time
        elapsed = time.time() - _last_request_time
        if elapsed < _ARXIV_RATE_LIMIT:
            time.sleep(_ARXIV_RATE_LIMIT - elapsed)
        _last_request_time = time.time()

        logger.info(f"arXiv 构建 PDF URL: ID={arxiv_id}")

        return FullTextResult(
            paper_id=paper_id, doi=doi, title=title,
            source=self.source_name,
            access_status="open_access", legal_status="legal_oa",
            pdf_url=pdf_url, landing_page_url=landing_page_url,
            risk_level="low",
        )

    def _clean_arxiv_id(self, arxiv_id: str) -> Optional[str]:
        arxiv_id = arxiv_id.strip()
        prefixes = [
            "https://arxiv.org/abs/", "http://arxiv.org/abs/",
            "https://arxiv.org/pdf/", "http://arxiv.org/pdf/",
            "arxiv:", "arXiv:",
        ]
        for prefix in prefixes:
            if arxiv_id.startswith(prefix):
                arxiv_id = arxiv_id[len(prefix):]
                break
        if arxiv_id.endswith(".pdf"):
            arxiv_id = arxiv_id[:-4]
        arxiv_id = arxiv_id.rstrip("/").strip()
        if _ARXIV_ID_PATTERN.match(arxiv_id):
            return arxiv_id
        return None
