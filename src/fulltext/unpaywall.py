"""
Unpaywall 全文解析器 — 通过 Unpaywall API 查询论文的 OA 版本。
"""

import time
from typing import Optional

import requests

from src.config import get_config
from src.fulltext.base import FullTextResult, FullTextResolver
from src.utils.logger import get_logger

logger = get_logger(__name__)

_UNPAYWALL_RATE_LIMIT = 1.0
_last_request_time: float = 0.0


class UnpaywallResolver(FullTextResolver):
    """
    Unpaywall 全文解析器。

    通过 DOI 调用 Unpaywall API 获取论文的合法 OA 版本信息。
    约束: 遵守速率限制，仅返回合法 OA 来源。
    """

    @property
    def source_name(self) -> str:
        return "unpaywall"

    def __init__(self):
        self.email = get_config("unpaywall.email", "")
        self.api_url = get_config("unpaywall.api_url", "https://api.unpaywall.org/v2")
        self.enabled = get_config("unpaywall.enabled", True)

    def resolve(self, paper: dict) -> FullTextResult:
        paper_id = paper.get("paper_id", paper.get("id", 0))
        doi = paper.get("doi")
        title = paper.get("title")

        if not self.enabled:
            return FullTextResult(
                paper_id=paper_id, doi=doi, title=title,
                source=self.source_name,
                access_status="unavailable", legal_status="unknown",
                error_message="Unpaywall 已禁用",
            )

        if not doi:
            return FullTextResult(
                paper_id=paper_id, doi=doi, title=title,
                source=self.source_name,
                access_status="unavailable", legal_status="unknown",
                error_message="论文无 DOI，无法通过 Unpaywall 查询",
            )

        # 速率限制
        global _last_request_time
        elapsed = time.time() - _last_request_time
        if elapsed < _UNPAYWALL_RATE_LIMIT:
            time.sleep(_UNPAYWALL_RATE_LIMIT - elapsed)

        url = f"{self.api_url}/{doi}"
        params = {"email": self.email} if self.email else {}

        logger.info(f"Unpaywall 查询: DOI={doi}")

        try:
            _last_request_time = time.time()
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            best_oa = data.get("best_oa_location") or {}
            pdf_url = best_oa.get("url_for_pdf")
            landing_page_url = best_oa.get("url_for_landing_page")
            oa_status = data.get("oa_status", "closed")

            if pdf_url and oa_status != "closed":
                logger.info(f"Unpaywall 找到 OA PDF: DOI={doi}, status={oa_status}")
                return FullTextResult(
                    paper_id=paper_id,
                    doi=doi,
                    title=title or data.get("title"),
                    source=self.source_name,
                    access_status="open_access",
                    legal_status="legal_oa",
                    pdf_url=pdf_url,
                    landing_page_url=landing_page_url,
                    risk_level="low",
                )

            logger.info(f"Unpaywall 未找到开放 PDF: DOI={doi}, oa_status={oa_status}")
            return FullTextResult(
                paper_id=paper_id,
                doi=doi,
                title=title or data.get("title"),
                source=self.source_name,
                access_status="unavailable",
                legal_status="unknown",
                pdf_url=None,
                landing_page_url=landing_page_url,
                error_message=f"Unpaywall oa_status={oa_status}, 无可用的 OA PDF",
            )

        except requests.exceptions.HTTPError as e:
            status_code = getattr(e.response, "status_code", 0)
            if status_code == 404:
                return FullTextResult(
                    paper_id=paper_id, doi=doi, title=title,
                    source=self.source_name,
                    access_status="unavailable", legal_status="unknown",
                    error_message=f"DOI 未在 Unpaywall 中找到 (HTTP 404)",
                )
            elif status_code == 429:
                return FullTextResult(
                    paper_id=paper_id, doi=doi, title=title,
                    source=self.source_name,
                    access_status="failed", legal_status="unknown",
                    error_message="Unpaywall API 速率限制 (HTTP 429)",
                )
            return FullTextResult(
                paper_id=paper_id, doi=doi, title=title,
                source=self.source_name,
                access_status="failed", legal_status="unknown",
                error_message=f"Unpaywall API 返回 HTTP {status_code}",
            )
        except requests.exceptions.Timeout:
            return FullTextResult(
                paper_id=paper_id, doi=doi, title=title,
                source=self.source_name,
                access_status="failed", legal_status="unknown",
                error_message="Unpaywall API 请求超时",
            )
        except Exception as e:
            logger.error(f"Unpaywall 查询异常: DOI={doi}, 原因={e}")
            return FullTextResult(
                paper_id=paper_id, doi=doi, title=title,
                source=self.source_name,
                access_status="failed", legal_status="unknown",
                error_message=f"Unpaywall 查询异常: {e}",
            )
