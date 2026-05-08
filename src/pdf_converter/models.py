"""Data models for PDF-to-Markdown conversion results."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PDFSection:
    heading: str
    level: int
    content: str
    start_page: int = 0


@dataclass
class PDFMetadata:
    title: str = ""
    authors: str = ""
    abstract: str = ""
    page_count: int = 0
    file_size_bytes: int = 0


@dataclass
class ConversionResult:
    paper_id: int | None = None
    pdf_path: str = ""
    md_path: str = ""
    title: str = ""
    abstract: str = ""
    sections: list[PDFSection] = field(default_factory=list)
    figures_count: int = 0
    tables_count: int = 0
    references_count: int = 0
    word_count: int = 0
    char_count: int = 0
    quality_score: int = 0
    status: str = "pending"
    error_message: str = ""
    engine: str = "pymupdf"
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "paper_id": self.paper_id,
            "pdf_path": self.pdf_path,
            "md_path": self.md_path,
            "title": self.title,
            "abstract": self.abstract,
            "sections": [{"heading": s.heading, "level": s.level, "start_page": s.start_page} for s in self.sections],
            "figures_count": self.figures_count,
            "tables_count": self.tables_count,
            "references_count": self.references_count,
            "word_count": self.word_count,
            "char_count": self.char_count,
            "quality_score": self.quality_score,
            "status": self.status,
            "error_message": self.error_message,
            "engine": self.engine,
            "created_at": self.created_at,
        }
