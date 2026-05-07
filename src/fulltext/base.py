"""
全文获取基础定义 — FullTextResult 数据类和 FullTextResolver 抽象基类。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class FullTextResult:
    """单次全文获取尝试的结果容器。"""

    paper_id: Optional[int] = None
    doi: Optional[str] = None
    title: Optional[str] = None

    # 获取来源
    source: str = ""
    access_mode: str = "api"
    legal_status: str = "unknown"

    # 获取状态
    success: bool = False
    access_status: str = "unavailable"

    # PDF 文件
    pdf_url: Optional[str] = None
    pdf_path: Optional[str] = None
    file_size: int = 0
    checksum_sha256: Optional[str] = None
    content_type: Optional[str] = None

    # 落地页
    landing_page_url: Optional[str] = None

    # 风险评估
    risk_level: str = "low"
    risk_note: Optional[str] = None

    # 错误信息
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


class FullTextResolver(ABC):
    """
    全文解析器抽象基类。

    每个解析器实现一个合法的全文获取途径:
      - UnpaywallResolver: 通过 Unpaywall API 查询 OA 状态和 PDF URL
      - PMCResolver: 通过 PubMed Central OA 子集获取
      - ArxivResolver: 通过 arXiv API 获取
      - PublisherOAResolver: 通过出版社 OA 接口获取
      - InstitutionAccessResolver: 通过机构网络授权获取
      - ManualUploadResolver: 用户手动上传 PDF

    法律边界:
      - 禁止绕过付费墙
      - 禁止使用 Sci-Hub 或类似服务
      - 机构订阅访问仅在检测到机构网络时启用
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """解析器名称，如 'unpaywall', 'pmc', 'arxiv'。"""
        ...

    @abstractmethod
    def resolve(self, paper: dict) -> FullTextResult:
        """
        尝试获取单篇论文的全文 PDF。

        Args:
            paper: 论文元数据字典，至少包含 paper_id, doi, title

        Returns:
            FullTextResult 结果容器
        """
        ...

    def can_handle(self, paper: dict) -> bool:
        """
        判断此解析器是否能处理该论文。

        默认返回 True，子类可重写以添加前置条件。
        """
        return True
