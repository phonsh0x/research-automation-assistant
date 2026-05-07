"""
全文获取模块 — 合法获取学术论文 PDF 全文。

组件:
  - FullTextResult: 全文获取结果数据类
  - FullTextResolver: 解析器抽象基类
  - FullTextAcquisitionService: 获取流程编排服务
  - 各解析器: Unpaywall、PMC、arXiv、Publisher OA、机构访问、人工上传
  - RestrictedSourceResolver: 受限来源拦截器

法律边界:
  - 仅通过合法开放 API 获取全文
  - 严禁使用 Sci-Hub 或任何绕过付费墙的手段
  - 所有下载记录写入 fulltext_access 表以供审计
"""

from src.fulltext.base import FullTextResult, FullTextResolver
from src.fulltext.downloader import download_pdf, validate_pdf_file as validate_pdf
from src.fulltext.unpaywall import UnpaywallResolver
from src.fulltext.pmc import PMCResolver
from src.fulltext.arxiv import ArxivResolver
from src.fulltext.publisher_oa import PublisherOAResolver
from src.fulltext.institution_access import InstitutionAccessResolver
from src.fulltext.manual_upload import ManualUploadResolver
from src.fulltext.restricted_sources import RestrictedSourceResolver
from src.fulltext.service import FullTextAcquisitionService

__all__ = [
    "FullTextResult",
    "FullTextResolver",
    "FullTextAcquisitionService",
    "UnpaywallResolver",
    "PMCResolver",
    "ArxivResolver",
    "PublisherOAResolver",
    "InstitutionAccessResolver",
    "ManualUploadResolver",
    "RestrictedSourceResolver",
    "download_pdf",
    "validate_pdf",
]
