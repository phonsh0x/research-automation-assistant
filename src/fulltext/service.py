"""
全文获取服务 — 统一协调所有 resolver 和下载流程。
"""

import time
from pathlib import Path
from typing import Optional

from src.config import get_config, get_data_path
from src.storage.repository import PaperRepository
from src.fulltext.base import FullTextResult, FullTextResolver
from src.fulltext.unpaywall import UnpaywallResolver
from src.fulltext.pmc import PMCResolver
from src.fulltext.arxiv import ArxivResolver
from src.fulltext.publisher_oa import PublisherOAResolver
from src.fulltext.institution_access import InstitutionAccessResolver
from src.fulltext.manual_upload import ManualUploadResolver
from src.fulltext.restricted_sources import RestrictedSourceResolver
from src.fulltext.downloader import download_pdf
from src.utils.logger import get_logger

logger = get_logger(__name__)


class FullTextAcquisitionService:
    """
    全文获取服务。

    协调所有 resolver 按优先级轮询，找到可用的 PDF 来源后执行下载，
    并更新数据库状态。

    工作流程:
      1. resolve() — 轮询 resolver 直到找到可用的 PDF URL
      2. download_pdf() — 下载 PDF 到 data/pdf/
      3. update_paper_pdf_status() — 更新 papers 表
      4. record_fulltext_access() — 记录 fulltext_access 表
      5. 返回 FullTextResult
    """

    def __init__(self, repository=None):
        """初始化全文获取服务。"""
        self.repository = repository or PaperRepository()
        self.pdf_dir = get_data_path(get_config("fulltext.pdf_dir", "data/pdf"))
        self.timeout = get_config("fulltext.timeout_seconds", 30)
        self.max_retries = get_config("fulltext.max_retries", 3)

        self.resolvers: list[FullTextResolver] = [
            UnpaywallResolver(),
            PMCResolver(),
            ArxivResolver(),
            PublisherOAResolver(),
            InstitutionAccessResolver(),
        ]

        self.restricted_source = RestrictedSourceResolver()

        logger.info(
            f"FullTextAcquisitionService 已初始化，resolver 数量={len(self.resolvers)}, "
            f"PDF 目录={self.pdf_dir}"
        )

    def resolve(self, paper_id: int, user_confirmed_institution: bool = False) -> FullTextResult:
        """查询合法全文来源（轮询所有 resolver 直到第一个返回可用 URL）。"""
        paper = self.repository.get_paper_by_id(paper_id)
        if not paper:
            return FullTextResult(
                paper_id=paper_id,
                access_status="failed", legal_status="unknown",
                error_message="该论文不存在",
            )

        logger.info(f"开始解析全文来源: paper_id={paper_id}")

        # 检查是否已有 PDF
        if paper.get("pdf_path") and paper.get("download_status") == "downloaded":
            return FullTextResult(
                paper_id=paper_id, doi=paper.get("doi"), title=paper.get("title"),
                source=paper.get("access_source", "unknown"),
                access_status="open_access",
                legal_status=paper.get("legal_status", "legal_oa"),
                pdf_url=paper.get("pdf_url"), pdf_path=paper.get("pdf_path"),
                risk_level="low",
            )

        # 检查 pdf_url 是否来自受限来源
        existing_pdf_url = paper.get("pdf_url")
        if existing_pdf_url and RestrictedSourceResolver.is_blocked_domain(existing_pdf_url):
            return self.restricted_source.resolve(paper)

        # 轮询 resolver
        for resolver in self.resolvers:
            try:
                logger.debug(f"尝试 resolver: {resolver.source_name}")
                result = resolver.resolve(paper)

                if result.pdf_url and result.access_status in ("open_access", "institution_access"):
                    logger.info(f"找到可用全文来源: resolver={result.source}, url={result.pdf_url[:100]}...")

                    if RestrictedSourceResolver.is_blocked_domain(result.pdf_url):
                        logger.warning(f"拦截受限源 URL: {result.pdf_url[:100]}...")
                        continue
                    return result

                if result.access_status == "institution_access" and result.pdf_url:
                    if not RestrictedSourceResolver.is_blocked_domain(result.pdf_url):
                        return result
            except Exception as e:
                logger.warning(f"Resolver {resolver.source_name} 异常: {e}")
                continue

        logger.info(f"所有 resolver 均未找到可用全文: paper_id={paper_id}")
        return FullTextResult(
            paper_id=paper_id, doi=paper.get("doi"), title=paper.get("title"),
            source="all_sources",
            access_status="unavailable", legal_status="unknown",
            error_message="所有合法来源均未找到可用全文",
        )

    def download(self, paper_id: int, user_confirmed_institution: bool = False) -> FullTextResult:
        """下载 PDF 并更新数据库。"""
        logger.info(f"开始下载全文: paper_id={paper_id}")

        result = self.resolve(paper_id, user_confirmed_institution)
        paper = self.repository.get_paper_by_id(paper_id)

        if not result.pdf_url:
            self._update_database(paper_id, result, paper)
            return result

        # 机构访问特殊流程
        if result.access_status == "institution_access" and result.source == "institution_access":
            if not user_confirmed_institution:
                result.access_status = "failed"
                result.error_message = "需要用户确认机构授权 (user_confirmed_institution=True)"
                self._update_database(paper_id, result, paper)
                return result

            inst_resolver = InstitutionAccessResolver()
            download_result = inst_resolver.download(
                paper=paper or {},
                save_dir=self.pdf_dir,
                user_confirmed_authorization=user_confirmed_institution,
            )

            if download_result.pdf_path:
                result.pdf_path = download_result.pdf_path
                result.file_size = download_result.file_size
                result.content_type = download_result.content_type
                result.checksum_sha256 = download_result.checksum_sha256
                result.access_status = download_result.access_status
                result.legal_status = download_result.legal_status
            else:
                result.access_status = download_result.access_status
                result.legal_status = download_result.legal_status
                result.error_message = download_result.error_message
                result.risk_level = download_result.risk_level
                result.risk_note = download_result.risk_note

            self._update_database(paper_id, result, paper)
            return result

        # 常规下载
        if result.pdf_url:
            if RestrictedSourceResolver.is_blocked_domain(result.pdf_url):
                result.access_status = "unsupported_source"
                result.legal_status = "unsupported"
                result.error_message = "该 URL 属于受限来源，已拦截"
                self._update_database(paper_id, result, paper)
                return result

            download_result = download_pdf(
                url=result.pdf_url,
                save_dir=self.pdf_dir,
                paper=paper or {},
                timeout=self.timeout,
                max_retries=self.max_retries,
            )

            if download_result["pdf_path"]:
                result.pdf_path = download_result["pdf_path"]
                result.file_size = download_result["file_size"]
                result.content_type = download_result["content_type"]
                result.checksum_sha256 = download_result["checksum_sha256"]
                logger.info(f"PDF 下载成功: paper_id={paper_id}")
            else:
                result.access_status = "failed"
                result.error_message = download_result.get("error_message", "下载失败")

        self._update_database(paper_id, result, paper)
        return result

    def batch_download(
        self, paper_ids: list[int],
        user_confirmed_institution: bool = False,
    ) -> list[FullTextResult]:
        """批量下载 PDF（不中断批量任务）。"""
        logger.info(f"开始批量下载: 共 {len(paper_ids)} 篇论文")
        results = []

        for i, paper_id in enumerate(paper_ids, start=1):
            logger.info(f"批量下载进度: {i}/{len(paper_ids)}, paper_id={paper_id}")
            try:
                result = self.download(paper_id, user_confirmed_institution)
                results.append(result)
            except Exception as e:
                logger.error(f"批量下载中单个论文失败: paper_id={paper_id}, 原因={e}")
                results.append(FullTextResult(
                    paper_id=paper_id,
                    access_status="failed", legal_status="unknown",
                    error_message=f"下载异常: {e}",
                ))

            if i < len(paper_ids):
                time.sleep(get_config("institution_access.request_interval_seconds", 8))

        downloaded = len([r for r in results if r.pdf_path])
        unavailable = len([r for r in results if r.access_status == "unavailable"])
        manual_review = len([r for r in results if r.access_status == "manual_review"])
        failed = len([r for r in results if r.access_status == "failed"])
        skipped = len([r for r in results if r.access_status == "skipped"])
        logger.info(
            f"批量下载完成: total={len(results)} downloaded={downloaded} "
            f"unavailable={unavailable} manual_review={manual_review} "
            f"failed={failed} skipped={skipped}"
        )
        return results

    # ==========================================================================
    # 便捷方法（向后兼容）
    # ==========================================================================

    def acquire_single(self, paper: dict) -> FullTextResult:
        """
        通过论文元数据字典获取全文（便捷方法）。

        Args:
            paper: 论文元数据字典，至少包含 paper_id

        Returns:
            FullTextResult 结果容器
        """
        paper_id = paper.get("paper_id") or paper.get("id")
        if not paper_id:
            return FullTextResult(
                paper_id=None,
                access_status="failed",
                error_message="论文数据不完整，无法获取全文",
            )
        return self.download(paper_id)

    def acquire_batch(self, limit: int = 20) -> list[FullTextResult]:
        """
        批量获取待下载论文的全文。

        Args:
            limit: 最大处理数量

        Returns:
            获取结果列表
        """
        papers = self.repository.get_papers_without_pdf(limit=limit)
        if not papers:
            logger.info("没有待下载 PDF 的论文。")
            return []

        paper_ids = [p.get("paper_id") or p.get("id") for p in papers if (p.get("paper_id") or p.get("id"))]
        return self.batch_download(paper_ids)

    def get_statistics(self) -> dict:
        """获取全文下载统计信息。"""
        return self.repository.get_download_statistics()

    # ==========================================================================
    # 私有方法
    # ==========================================================================

    def _update_database(self, paper_id: int, result: FullTextResult, paper: Optional[dict]) -> None:
        """更新数据库中的全文状态（papers 表 + fulltext_access 表）。"""
        try:
            if result.pdf_path:
                download_status = "downloaded"
            elif result.access_status == "failed":
                download_status = "failed"
            elif result.access_status == "manual_review":
                download_status = "manual_review"
            elif result.access_status == "unsupported_source":
                download_status = "failed"
            elif result.access_status == "unavailable":
                download_status = "unavailable"
            else:
                download_status = "pending"

            self.repository.update_paper_pdf_status(
                paper_id=paper_id,
                pdf_path=result.pdf_path,
                download_status=download_status,
                access_source=result.source,
                legal_status=result.legal_status,
                oa_status=result.access_status if result.access_status == "open_access" else None,
                pdf_url=result.pdf_url,
                error_message=result.error_message,
            )

            self.repository.record_fulltext_access(
                paper_id=paper_id,
                doi=result.doi or (paper.get("doi") if paper else None),
                title=result.title or (paper.get("title") if paper else None),
                access_status=result.access_status,
                access_source=result.source,
                access_mode="api",
                legal_status=result.legal_status,
                pdf_url=result.pdf_url,
                landing_page_url=result.landing_page_url,
                pdf_path=result.pdf_path,
                file_size=result.file_size,
                checksum_sha256=result.checksum_sha256,
                content_type=result.content_type,
                risk_level=result.risk_level,
                risk_note=result.risk_note,
                error_message=result.error_message,
            )

            logger.info(f"数据库已更新: paper_id={paper_id}, status={download_status}")
        except Exception as e:
            logger.error(f"更新数据库失败: paper_id={paper_id}, 原因={e}")
