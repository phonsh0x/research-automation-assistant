"""
文献检索数据模型 — 定义统一的文献元数据结构。

所有外部 API 返回的结果均转换为此格式，确保后续模块处理一致性。
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PaperMetadata:
    """
    标准化的文献元数据。

    各字段对应于数据库 papers 表的列，便于直接入库。
    """
    title: str                              # 论文标题
    authors: list[str] = field(default_factory=list)   # 作者列表（全名）
    doi: Optional[str] = None               # DOI
    arxiv_id: Optional[str] = None          # arXiv ID
    pmid: Optional[str] = None              # PubMed ID
    pmcid: Optional[str] = None             # PubMed Central ID
    year: Optional[int] = None              # 发表年份
    journal: Optional[str] = None           # 期刊/会议名称
    volume: Optional[str] = None            # 卷号
    issue: Optional[str] = None             # 期号
    pages: Optional[str] = None             # 页码
    publisher: Optional[str] = None         # 出版社
    abstract: Optional[str] = None          # 摘要
    keywords: list[str] = field(default_factory=list)   # 关键词列表
    language: str = "en"                    # 语言
    citation_count: int = 0                 # 引用次数
    source_api: str = ""                    # 来源 API 名称（openalex/crossref/pubmed/arxiv）
    source_id: Optional[str] = None         # 来源系统中的 ID
    oa_status: str = "unknown"              # OA 状态：gold/green/hybrid/bronze/closed/unknown
    oa_url: Optional[str] = None            # 开放获取 PDF URL

    def to_dict(self) -> dict:
        """转换为字典，用于数据库插入。"""
        return {
            "title": self.title,
            "abstract": self.abstract,
            "doi": self.doi,
            "arxiv_id": self.arxiv_id,
            "pmid": self.pmid,
            "pmcid": self.pmcid,
            "year": self.year,
            "journal": self.journal,
            "volume": self.volume,
            "issue": self.issue,
            "pages": self.pages,
            "publisher": self.publisher,
            "language": self.language,
            "citation_count": self.citation_count,
            "oa_status": self.oa_status,
            "source_api": self.source_api,
            "source_id": self.source_id,
        }

    def __str__(self) -> str:
        authors_str = ", ".join(self.authors[:3])
        if len(self.authors) > 3:
            authors_str += f" 等 ({len(self.authors)}人)"
        return (
            f"PaperMetadata(title='{self.title[:80]}...', "
            f"authors='{authors_str}', "
            f"year={self.year}, journal='{self.journal}', "
            f"oa_status='{self.oa_status}')"
        )


@dataclass
class SearchQuery:
    """检索查询参数。"""
    keywords: str                           # 查询关键词
    max_results: int = 20                   # 最大结果数
    year_from: Optional[int] = None         # 起始年份
    year_to: Optional[int] = None           # 结束年份
    sources: list[str] = field(default_factory=lambda: ["openalex"])  # 使用的 API 列表
    sort_by: str = "relevance"              # 排序方式：relevance/year/citations
    filter_oa_only: bool = False            # 是否仅返回 OA 文献
