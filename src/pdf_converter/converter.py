"""PDF-to-Markdown converter — PyMuPDF-based extraction pipeline."""

import re
from datetime import datetime
from pathlib import Path

import fitz

from src.config import get_config, get_data_path
from src.pdf_converter.models import ConversionResult, PDFMetadata, PDFSection
from src.pdf_converter.quality import compute_quality_score
from src.utils.logger import get_logger

_log = get_logger(__name__)

# Common heading patterns in academic papers
_HEADING_RE = re.compile(
    r"^\s*(?:\d+\.?\s+)?(?:Introduction|Abstract|Background|Methods?|"
    r"Materials?\s*(?:and\s*Methods?)?|Results?\s*(?:and\s*Discussion)?|"
    r"Discussion|Conclusion|References?|Bibliography|Acknowledgments?|"
    r"Supplementary|Appendix|Related\s+Work|Future\s+Work|Experiments?)",
    re.IGNORECASE,
)


class PDFConverter:
    """Convert academic PDFs to structured Markdown using PyMuPDF."""

    def __init__(self, engine: str = "pymupdf"):
        self.engine = engine
        self.output_dir = get_data_path(get_config("pdf_conversion.output_dir", "data/markdown"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        _log.info("PDFConverter initialised with engine=%s", engine)

    def convert(self, pdf_path: Path) -> ConversionResult:
        """Convert a single PDF to Markdown."""
        result = ConversionResult(
            pdf_path=str(pdf_path),
            engine=self.engine,
            created_at=datetime.now().isoformat(),
        )

        if not pdf_path.exists():
            result.status = "failed"
            result.error_message = f"PDF file not found: {pdf_path}"
            return result

        try:
            doc = fitz.open(str(pdf_path))
        except Exception as exc:
            result.status = "failed"
            result.error_message = f"Cannot open PDF: {exc}"
            _log.error("Failed to open PDF: %s — %s", pdf_path, exc)
            return result

        try:
            metadata = self._extract_metadata(doc)
            sections = self._extract_sections(doc)
            full_text = self._build_markdown(metadata, sections)

            md_filename = pdf_path.stem + ".md"
            md_path = self.output_dir / md_filename
            md_path.write_text(full_text, encoding="utf-8")

            word_count = len(full_text.split())
            char_count = len(full_text)

            result.md_path = str(md_path)
            result.title = metadata.title
            result.abstract = metadata.abstract
            result.sections = sections
            result.figures_count = 0
            result.tables_count = 0
            result.references_count = self._count_references(full_text)
            result.word_count = word_count
            result.char_count = char_count
            result.status = "success"
            result.quality_score = compute_quality_score(result)

            _log.info(
                "Converted %s — chars=%d words=%d sections=%d score=%d",
                pdf_path.name, char_count, word_count, len(sections),
                result.quality_score,
            )
        except Exception as exc:
            result.status = "failed"
            result.error_message = f"Conversion error: {exc}"
            _log.error("Conversion failed for %s: %s", pdf_path, exc)
        finally:
            doc.close()

        return result

    def batch_convert(self, pdf_paths: list[Path]) -> list[ConversionResult]:
        """Convert multiple PDFs sequentially."""
        results = []
        for i, path in enumerate(pdf_paths, start=1):
            _log.info("Batch convert %d/%d: %s", i, len(pdf_paths), path.name)
            results.append(self.convert(path))
        return results

    # ------------------------------------------------------------------
    # Private extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_metadata(doc: fitz.Document) -> PDFMetadata:
        meta = PDFMetadata(page_count=doc.page_count)
        if doc.page_count == 0:
            return meta

        first_page_text = doc[0].get_text("text").strip()
        lines = [l.strip() for l in first_page_text.splitlines() if l.strip()]

        # Heuristic: first non-empty substantial line is the title
        for line in lines[:10]:
            if len(line) > 15 and not line.startswith(("©", "http", "DOI")):
                meta.title = line[:200]
                break

        # Heuristic: abstract block
        full_text = "\n".join(lines)
        abs_match = re.search(
            r"(?:Abstract|ABSTRACT|摘要)\s*\n+(.*?)(?:\n\s*(?:Introduction|INTRODUCTION|1\.?\s|Keywords|KEYWORDS))",
            full_text, re.DOTALL,
        )
        if abs_match:
            meta.abstract = abs_match.group(1).strip()[:2000]

        meta.file_size_bytes = doc.metadata.get("fileSize", 0) if hasattr(doc, "metadata") else 0
        return meta

    @staticmethod
    def _extract_sections(doc: fitz.Document) -> list[PDFSection]:
        sections = []
        current_section = None

        for page_num in range(doc.page_count):
            text = doc[page_num].get_text("text")
            for line in text.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue

                if _HEADING_RE.match(stripped):
                    if current_section:
                        sections.append(current_section)
                    level = 2 if len(stripped) < 30 else 3
                    current_section = PDFSection(
                        heading=stripped,
                        level=level,
                        content="",
                        start_page=page_num + 1,
                    )
                elif current_section:
                    current_section.content += stripped + "\n"

        if current_section:
            sections.append(current_section)

        return sections

    @staticmethod
    def _build_markdown(metadata: PDFMetadata, sections: list[PDFSection]) -> str:
        lines = []

        # Title
        if metadata.title:
            lines.append(f"# {metadata.title}\n")
        lines.append(f"> Converted by ResearchAutomationAssistant | Pages: {metadata.page_count}\n")

        # Abstract
        if metadata.abstract:
            lines.append("## Abstract\n")
            lines.append(metadata.abstract + "\n")

        # Main text
        lines.append("## Main Text\n")
        for sec in sections:
            prefix = "#" * sec.level
            lines.append(f"{prefix} {sec.heading}\n")
            lines.append(sec.content.strip() + "\n")

        # References placeholder
        lines.append("## References\n")
        lines.append("*(Auto-extracted — manual verification recommended)*\n")

        return "\n".join(lines)

    @staticmethod
    def _count_references(text: str) -> int:
        """Rough count of reference entries."""
        ref_match = re.search(
            r"(?:References?|Bibliography|REFERENCES)\s*\n(.*?)$",
            text, re.DOTALL | re.IGNORECASE,
        )
        if ref_match:
            ref_text = ref_match.group(1)
            return len([l for l in ref_text.splitlines() if l.strip() and len(l.strip()) > 10])
        return 0
