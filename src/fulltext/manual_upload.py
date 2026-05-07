"""
手动上传解析器 — 接受用户提供的本地 PDF 文件，复制到 data/pdf/ 目录。
"""

import shutil
from pathlib import Path
from typing import Optional

from src.config import get_config
from src.fulltext.base import FullTextResult, FullTextResolver
from src.fulltext.downloader import validate_pdf_file, compute_sha256, build_pdf_filename
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ManualUploadResolver(FullTextResolver):
    """
    手动上传解析器。

    功能:
      - 接收本地 PDF 文件路径
      - 验证文件是有效 PDF
      - 复制到 data/pdf/ 目录
      - 计算 SHA256 校验和
    约束: 用户需确认有权在课题组内部使用该 PDF。
    """

    @property
    def source_name(self) -> str:
        return "manual_upload"

    def __init__(self):
        self.enabled = get_config("manual_upload.enabled", True)
        self.require_confirmation = get_config("manual_upload.require_rights_confirmation", True)
        self.pdf_dir = get_config("fulltext.pdf_dir", "data/pdf")

    def resolve(self, paper: dict) -> FullTextResult:
        paper_id = paper.get("paper_id", paper.get("id", 0))
        return FullTextResult(
            paper_id=paper_id, doi=paper.get("doi"), title=paper.get("title"),
            source=self.source_name,
            access_status="unavailable", legal_status="unknown",
            error_message="请使用 upload() 方法上传 PDF 文件。",
        )

    def upload(
        self,
        paper: dict,
        source_pdf_path: str,
        pdf_dir: Optional[Path] = None,
        user_confirmed_rights: bool = False,
    ) -> FullTextResult:
        """上传本地 PDF 文件到 data/pdf/ 目录。"""
        paper_id = paper.get("paper_id", paper.get("id", 0))
        doi = paper.get("doi")
        title = paper.get("title")

        if not self.enabled:
            return FullTextResult(
                paper_id=paper_id, doi=doi, title=title,
                source=self.source_name,
                access_status="unavailable", legal_status="unknown",
                error_message="手动上传功能已禁用",
            )

        if self.require_confirmation and not user_confirmed_rights:
            return FullTextResult(
                paper_id=paper_id, doi=doi, title=title,
                source=self.source_name,
                access_status="failed", legal_status="unknown",
                error_message="需要用户确认有权在课题组内部使用该 PDF",
            )

        source_path = Path(source_pdf_path)
        if not source_path.exists() or not source_path.is_file():
            return FullTextResult(
                paper_id=paper_id, doi=doi, title=title,
                source=self.source_name,
                access_status="failed", legal_status="unknown",
                error_message=f"源文件无效: {source_pdf_path}",
            )

        if not validate_pdf_file(source_path):
            return FullTextResult(
                paper_id=paper_id, doi=doi, title=title,
                source=self.source_name,
                access_status="failed", legal_status="unknown",
                error_message="源文件不是有效的 PDF",
            )

        file_size = source_path.stat().st_size
        if file_size < 10240:
            return FullTextResult(
                paper_id=paper_id, doi=doi, title=title,
                source=self.source_name,
                access_status="failed", legal_status="unknown",
                error_message=f"PDF 文件过小 ({file_size} 字节)",
            )

        if pdf_dir is None:
            from src.config import get_data_path
            target_dir = get_data_path(self.pdf_dir)
        else:
            target_dir = Path(pdf_dir)

        target_dir.mkdir(parents=True, exist_ok=True)

        filename = build_pdf_filename(paper)
        target_path = target_dir / filename

        try:
            shutil.copy2(source_path, target_path)
            logger.info(f"PDF 已复制: {source_path} -> {target_path}")
        except Exception as e:
            return FullTextResult(
                paper_id=paper_id, doi=doi, title=title,
                source=self.source_name,
                access_status="failed", legal_status="unknown",
                error_message=f"文件复制失败: {e}",
            )

        checksum = compute_sha256(target_path)

        logger.info(f"手动上传成功: paper_id={paper_id}, path={target_path}, size={file_size}")
        return FullTextResult(
            paper_id=paper_id, doi=doi, title=title,
            source=self.source_name,
            access_status="manual_upload", legal_status="user_provided",
            pdf_path=str(target_path), file_size=file_size,
            content_type="application/pdf", checksum_sha256=checksum,
            risk_level="low",
        )
