"""Phase 2.3 PDF-to-Markdown conversion tests."""

import tempfile
from pathlib import Path

import fitz


# ============================================================================
# Helpers
# ============================================================================

def _create_minimal_pdf(path: Path, text: str = "Test content") -> Path:
    """Create a minimal valid PDF with one page of text."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    doc.save(str(path))
    doc.close()
    return path


# ============================================================================
# Data models
# ============================================================================

class TestConversionResult:
    def test_defaults(self):
        from src.pdf_converter.models import ConversionResult
        r = ConversionResult()
        assert r.status == "pending"
        assert r.pdf_path == ""
        assert r.quality_score == 0

    def test_to_dict(self):
        from src.pdf_converter.models import ConversionResult
        r = ConversionResult(paper_id=1, pdf_path="/tmp/a.pdf", status="success", char_count=500, word_count=80)
        d = r.to_dict()
        assert d["paper_id"] == 1
        assert d["status"] == "success"
        assert d["char_count"] == 500
        assert d["word_count"] == 80

    def test_pdf_metadata(self):
        from src.pdf_converter.models import PDFMetadata
        m = PDFMetadata(title="Test Title", abstract="Abstract text", page_count=3)
        assert m.title == "Test Title"
        assert m.page_count == 3


class TestPDFSection:
    def test_section_fields(self):
        from src.pdf_converter.models import PDFSection
        s = PDFSection(heading="Introduction", level=2, content="Some text.", start_page=1)
        assert s.heading == "Introduction"
        assert s.level == 2
        assert s.start_page == 1


# ============================================================================
# Converter
# ============================================================================

class TestPDFConverter:
    def test_missing_file_returns_failed(self, tmp_path):
        from src.pdf_converter import PDFConverter
        c = PDFConverter()
        result = c.convert(tmp_path / "nonexistent.pdf")
        assert result.status == "failed"
        assert "not found" in result.error_message

    def test_valid_pdf_converts(self, tmp_path):
        from src.pdf_converter import PDFConverter
        pdf_path = _create_minimal_pdf(tmp_path / "test.pdf", "This is a minimal PDF for testing conversion.")
        c = PDFConverter()
        c.output_dir = tmp_path / "md"
        c.output_dir.mkdir()

        result = c.convert(pdf_path)
        assert result.status == "success", f"Error: {result.error_message}"
        assert result.char_count > 0
        assert result.word_count > 0
        assert Path(result.md_path).exists()

    def test_converted_md_has_expected_structure(self, tmp_path):
        from src.pdf_converter import PDFConverter
        text = "Abstract\nThis is the abstract.\nIntroduction\nWe present a new method."
        pdf_path = _create_minimal_pdf(tmp_path / "struct.pdf", text)
        c = PDFConverter()
        c.output_dir = tmp_path / "md"
        c.output_dir.mkdir()

        result = c.convert(pdf_path)
        assert result.status == "success"
        md_content = Path(result.md_path).read_text(encoding="utf-8")
        assert "## Main Text" in md_content or "## Abstract" in md_content

    def test_paper_id_set_on_result(self, tmp_path):
        from src.pdf_converter import PDFConverter
        pdf_path = _create_minimal_pdf(tmp_path / "id_test.pdf", "Minimal content.")
        c = PDFConverter()
        c.output_dir = tmp_path / "md"
        c.output_dir.mkdir()

        result = c.convert(pdf_path)
        result.paper_id = 42
        d = result.to_dict()
        assert d["paper_id"] == 42

    def test_batch_convert(self, tmp_path):
        from src.pdf_converter import PDFConverter
        paths = []
        for i in range(3):
            p = _create_minimal_pdf(tmp_path / f"batch_{i}.pdf", f"Content page {i}.")
            paths.append(p)
        c = PDFConverter()
        c.output_dir = tmp_path / "md"
        c.output_dir.mkdir()

        results = c.batch_convert(paths)
        assert len(results) == 3
        assert all(r.status == "success" for r in results)


# ============================================================================
# Quality scoring
# ============================================================================

class TestQualityScore:
    def test_good_content_scores_high(self):
        from src.pdf_converter import ConversionResult
        from src.pdf_converter.quality import compute_quality_score
        r = ConversionResult(
            title="A Good Paper", abstract="Some abstract",
            char_count=2000, word_count=400, sections=[
                __import__("src.pdf_converter.models", fromlist=["PDFSection"]).PDFSection("Intro", 2, ""),
                __import__("src.pdf_converter.models", fromlist=["PDFSection"]).PDFSection("Methods", 2, ""),
                __import__("src.pdf_converter.models", fromlist=["PDFSection"]).PDFSection("Results", 2, ""),
            ],
        )
        score = compute_quality_score(r)
        assert score >= 60

    def test_poor_content_scores_low(self):
        from src.pdf_converter import ConversionResult
        from src.pdf_converter.quality import compute_quality_score
        r = ConversionResult(char_count=10, word_count=2)
        score = compute_quality_score(r)
        assert score < 40

    def test_needs_review_threshold(self):
        from src.pdf_converter.quality import needs_review
        assert needs_review(30) is True
        assert needs_review(60) is False


# ============================================================================
# Repository methods
# ============================================================================

class TestRepositoryConversion:
    def test_get_papers_with_pdf_without_md(self):
        from src.storage.repository import PaperRepository
        from src.paper_search.models import PaperMetadata

        repo = PaperRepository()
        paper = PaperMetadata(title="PDF Paper", doi="10.9999/pdf.2026", year=2026, source_api="test")
        pid, _ = repo.upsert_paper(paper)
        repo.update_paper_pdf_status(pid, pdf_path="/tmp/test.pdf", download_status="downloaded")

        papers = repo.get_papers_with_pdf_without_markdown(limit=5)
        assert any(p["paper_id"] == pid for p in papers)

    def test_update_paper_markdown_status(self):
        from src.storage.repository import PaperRepository
        from src.paper_search.models import PaperMetadata

        repo = PaperRepository()
        paper = PaperMetadata(title="MD Update Paper", doi="10.9999/md.2026", year=2026, source_api="test")
        pid, _ = repo.upsert_paper(paper)

        ok = repo.update_paper_markdown_status(pid, "/tmp/test.md")
        assert ok is True

    def test_record_full_text(self):
        from src.storage.repository import PaperRepository
        from src.paper_search.models import PaperMetadata
        from src.pdf_converter.models import ConversionResult

        repo = PaperRepository()
        paper = PaperMetadata(title="FT Record Paper", doi="10.9999/ft.2026", year=2026, source_api="test")
        pid, _ = repo.upsert_paper(paper)

        result = ConversionResult(paper_id=pid, char_count=1000, word_count=200, status="success")
        ok = repo.record_full_text(result)
        assert ok is True

    def test_get_conversion_statistics(self):
        from src.storage.repository import PaperRepository
        repo = PaperRepository()
        stats = repo.get_conversion_statistics()
        assert "with_pdf" in stats
        assert "with_markdown" in stats
        assert "pending" in stats


# ============================================================================
# UI service
# ============================================================================

class TestUIConversionService:
    def test_get_conversion_stats_returns_structure(self):
        from ui.services.pdf_convert_ui_service import get_conversion_stats
        result = get_conversion_stats()
        assert result["success"] is True
        assert "with_pdf" in result["data"]

    def test_get_pending_papers_returns_structure(self):
        from ui.services.pdf_convert_ui_service import get_pending_papers
        result = get_pending_papers(limit=5)
        assert result["success"] is True
        assert "papers" in result["data"]

    def test_convert_single_no_pdf(self):
        from ui.services.pdf_convert_ui_service import convert_single
        result = convert_single(99999999)
        # Should fail gracefully — missing paper or no PDF
        assert result["success"] is False
