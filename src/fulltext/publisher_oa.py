"""
出版社 OA 全文解析器 — 处理已在 papers 表中标记为 gold/hybrid/bronze 的论文。
"""

from src.fulltext.base import FullTextResult, FullTextResolver
from src.fulltext.downloader import validate_url
from src.utils.logger import get_logger

logger = get_logger(__name__)

_LEGAL_OA_STATUSES = {"gold", "hybrid", "bronze"}


class PublisherOAResolver(FullTextResolver):
    """
    出版社 OA 解析器。

    仅处理 papers 表中 oa_status 已标记为 gold/hybrid/bronze 的论文。
    使用 papers 表中的 pdf_url 字段。
    约束: 不绕过任何付费墙，下载前校验 URL。
    """

    @property
    def source_name(self) -> str:
        return "publisher_oa"

    def resolve(self, paper: dict) -> FullTextResult:
        paper_id = paper.get("paper_id", paper.get("id", 0))
        doi = paper.get("doi")
        title = paper.get("title")
        oa_status = paper.get("oa_status", "").lower()
        pdf_url = paper.get("pdf_url")

        if oa_status not in _LEGAL_OA_STATUSES:
            return FullTextResult(
                paper_id=paper_id, doi=doi, title=title,
                source=self.source_name,
                access_status="unavailable", legal_status="unknown",
                error_message=f"OA 状态不是 gold/hybrid/bronze (当前: {oa_status})",
            )

        if not pdf_url:
            pdf_url = paper.get("oa_url") or paper.get("source_url") or paper.get("landing_page_url")

        if not pdf_url:
            return FullTextResult(
                paper_id=paper_id, doi=doi, title=title,
                source=self.source_name,
                access_status="unavailable", legal_status="unknown",
                error_message="论文虽标记为 OA，但无可用 PDF URL",
            )

        if not validate_url(pdf_url):
            return FullTextResult(
                paper_id=paper_id, doi=doi, title=title,
                source=self.source_name,
                access_status="unavailable", legal_status="unknown",
                error_message=f"出版社 OA URL 校验失败: {pdf_url[:100]}",
            )

        logger.info(f"出版社 OA 已就绪: paper_id={paper_id}, oa_status={oa_status}")
        return FullTextResult(
            paper_id=paper_id, doi=doi, title=title,
            source=self.source_name,
            access_status="open_access", legal_status="legal_oa",
            pdf_url=pdf_url,
            landing_page_url=paper.get("landing_page_url"),
            risk_level="low",
        )
