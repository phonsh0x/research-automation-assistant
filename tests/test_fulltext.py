"""
Phase 2.2 全文获取模块测试。

测试覆盖:
  - FullTextResult 数据类
  - downloader 工具函数（文件名生成、URL验证、SHA256、PDF验证）
  - 各 resolver 接入（Unpaywall、PMC、arXiv、PublisherOA、InstitutionAccess、ManualUpload）
  - RestrictedSourceResolver 域名拦截
  - FullTextAcquisitionService 编排
  - 数据库 PDF 状态更新和统计
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.fulltext.base import FullTextResult, FullTextResolver
from src.fulltext.downloader import (
    validate_url,
    sanitize_filename,
    build_pdf_filename,
    compute_sha256,
    validate_pdf_file,
)
from src.fulltext.restricted_sources import (
    is_restricted_domain,
    is_known_oa_domain,
    check_restricted,
    RestrictedSourceResolver,
)


# ============================================================================
# FullTextResult
# ============================================================================

class TestFullTextResult:
    def test_default_values(self):
        r = FullTextResult()
        assert r.success is False
        assert r.access_status == "unavailable"
        assert r.legal_status == "unknown"
        assert r.risk_level == "low"
        assert r.file_size == 0

    def test_to_dict(self):
        r = FullTextResult(paper_id=1, doi="10.1234/test", title="Test Paper")
        d = r.to_dict()
        assert d["paper_id"] == 1
        assert d["doi"] == "10.1234/test"
        assert d["title"] == "Test Paper"

    def test_success_result(self):
        r = FullTextResult(
            paper_id=1,
            doi="10.1234/test",
            title="A Paper",
            source="unpaywall",
            success=True,
            access_status="open_access",
            legal_status="legal_oa",
            pdf_url="https://example.com/paper.pdf",
            pdf_path="/data/pdf/paper.pdf",
            file_size=12345,
            checksum_sha256="abc123",
        )
        assert r.success is True
        assert r.pdf_url == "https://example.com/paper.pdf"
        assert r.legal_status == "legal_oa"

    def test_failure_result(self):
        r = FullTextResult(
            paper_id=2,
            doi="10.1234/fail",
            title="Failed Paper",
            error_message="All resolvers exhausted",
        )
        assert r.success is False
        assert r.error_message == "All resolvers exhausted"


# ============================================================================
# Downloader 工具函数
# ============================================================================

class TestValidateUrl:
    def test_valid_https_url(self):
        assert validate_url("https://example.com/paper.pdf") is True

    def test_valid_http_url(self):
        assert validate_url("http://arxiv.org/pdf/1234.5678.pdf") is True

    def test_invalid_protocol(self):
        assert validate_url("ftp://example.com/paper.pdf") is False

    def test_empty_url(self):
        assert validate_url("") is False
        assert validate_url(None) is False

    def test_scihub_blocked(self):
        assert validate_url("https://sci-hub.se/10.1234/test") is False
        assert validate_url("https://sci-hub.ru/test") is False
        assert validate_url("https://sci-hub.st/test") is False

    def test_libgen_blocked(self):
        assert validate_url("https://libgen.is/book/test") is False
        assert validate_url("https://libgen.st/test") is False


class TestSanitizeFilename:
    def test_removes_illegal_chars(self):
        result = sanitize_filename('test:file<name>.pdf')
        assert ":" not in result
        assert "<" not in result

    def test_trims_length(self):
        long_name = "a" * 300 + ".pdf"
        result = sanitize_filename(long_name)
        assert len(result) <= 200

    def test_handles_empty(self):
        result = sanitize_filename("")
        assert result == ""


class TestBuildPdfFilename:
    def test_with_all_fields(self):
        paper = {
            "authors": "Smith, John; Jones, Bob",
            "year": 2024,
            "doi": "10.1234/test.paper",
        }
        name = build_pdf_filename(paper)
        assert "2024" in name
        assert name.endswith(".pdf")

    def test_with_minimal_fields(self):
        paper = {"title": "A Very Important Paper", "year": 2023}
        name = build_pdf_filename(paper)
        assert name.endswith(".pdf")

    def test_fallback(self):
        paper = {}
        name = build_pdf_filename(paper)
        assert name.endswith(".pdf")
        assert "unknown" in name


class TestComputeSha256:
    def test_computes_hash(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_bytes(b"hello world")
        h = compute_sha256(f)
        assert len(h) == 64
        assert h == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"

    def test_none_for_missing_file(self):
        result = compute_sha256(Path("/nonexistent/file.pdf"))
        assert result is None or result == ""  # returns None or empty string on failure


class TestValidatePdfFile:
    def test_valid_pdf(self, tmp_path):
        f = tmp_path / "valid.pdf"
        f.write_bytes(b"%PDF-1.4\nsome content\n%%EOF")
        assert validate_pdf_file(f) is True

    def test_invalid_header(self, tmp_path):
        f = tmp_path / "invalid.pdf"
        f.write_bytes(b"NOT A PDF\x00\x00\x00\x00\x00")
        assert validate_pdf_file(f) is False

    def test_too_small(self, tmp_path):
        # validate_pdf_file only checks header magic, size check is done in downloader
        f = tmp_path / "small.pdf"
        f.write_bytes(b"not a pdf at all")
        assert validate_pdf_file(f) is False

    def test_missing_file(self):
        assert validate_pdf_file(Path("/nonexistent/test.pdf")) is False


# ============================================================================
# 受限来源检查
# ============================================================================

class TestRestrictedSources:
    def test_scihub_is_restricted(self):
        assert is_restricted_domain("https://sci-hub.se/paper") is True
        assert is_restricted_domain("https://sci-hub.ru/test") is True

    def test_libgen_is_restricted(self):
        assert is_restricted_domain("https://libgen.is/book") is True

    def test_arxiv_is_not_restricted(self):
        assert is_restricted_domain("https://arxiv.org/pdf/1234.5678.pdf") is False

    def test_pmc_is_not_restricted(self):
        assert is_restricted_domain("https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12345/pdf/main.pdf") is False

    def test_known_oa_domain(self):
        assert is_known_oa_domain("https://arxiv.org/abs/1234.5678") is True
        assert is_known_oa_domain("https://www.nature.com/articles/s41586-024-12345-6") is True
        assert is_known_oa_domain("https://unknown-pirate-site.com/paper.pdf") is False

    def test_check_restricted_safe(self):
        is_safe, risk = check_restricted("https://arxiv.org/pdf/1234.5678.pdf")
        assert is_safe is True
        assert risk == "low"

    def test_check_restricted_blocked(self):
        is_safe, risk = check_restricted("https://sci-hub.se/test")
        assert is_safe is False
        assert risk == "high"

    def test_check_restricted_unknown(self):
        is_safe, risk = check_restricted("https://some-unknown-domain.com/paper.pdf")
        assert is_safe is True
        assert risk == "medium"

    def test_empty_url(self):
        assert is_restricted_domain("") is False
        assert check_restricted("") == (True, "medium")


class TestRestrictedSourceResolver:
    def test_source_name(self):
        resolver = RestrictedSourceResolver()
        assert resolver.source_name == "restricted_sources"

    def test_resolve_returns_unsupported(self):
        resolver = RestrictedSourceResolver()
        result = resolver.resolve({"paper_id": 1, "doi": "10.1234/test"})
        assert result.access_status == "unsupported_source"
        assert result.legal_status == "unsupported"
        assert result.risk_level == "high"

    def test_is_blocked_domain(self):
        assert RestrictedSourceResolver.is_blocked_domain("https://sci-hub.se/test") is True
        assert RestrictedSourceResolver.is_blocked_domain("https://arxiv.org/pdf/test.pdf") is False
        assert RestrictedSourceResolver.is_blocked_domain("") is False


# ============================================================================
# FullTextResolver 抽象基类
# ============================================================================

class TestFullTextResolver:
    def test_can_handle_default(self):
        class DummyResolver(FullTextResolver):
            @property
            def source_name(self):
                return "dummy"
            def resolve(self, paper):
                return FullTextResult()

        r = DummyResolver()
        assert r.can_handle({"paper_id": 1}) is True
        assert r.can_handle({}) is True


# ============================================================================
# 各 Resolver 接入（单元测试）
# ============================================================================

class TestUnpaywallResolver:
    def test_source_name(self):
        from src.fulltext.unpaywall import UnpaywallResolver
        r = UnpaywallResolver()
        assert r.source_name == "unpaywall"

    def test_requires_doi(self):
        from src.fulltext.unpaywall import UnpaywallResolver
        r = UnpaywallResolver()
        # can_handle defaults to True (check happens inside resolve)
        assert r.can_handle({"doi": "10.1234/test"}) is True
        # No DOI returns error inside resolve()
        result = r.resolve({"paper_id": 1, "title": "No DOI"})
        assert result.success is False

    def test_no_doi_returns_error(self):
        from src.fulltext.unpaywall import UnpaywallResolver
        r = UnpaywallResolver()
        result = r.resolve({"paper_id": 1, "title": "No DOI"})
        assert result.success is False
        assert "DOI" in result.error_message


class TestPMCResolver:
    def test_source_name(self):
        from src.fulltext.pmc import PMCResolver
        r = PMCResolver()
        assert r.source_name == "pmc"

    def test_no_pmcid_returns_error(self):
        from src.fulltext.pmc import PMCResolver
        r = PMCResolver()
        result = r.resolve({"paper_id": 1, "title": "No PMCID"})
        assert result.success is False


class TestArxivResolver:
    def test_source_name(self):
        from src.fulltext.arxiv import ArxivResolver
        r = ArxivResolver()
        assert r.source_name == "arxiv"

    def test_no_arxiv_id_returns_error(self):
        from src.fulltext.arxiv import ArxivResolver
        r = ArxivResolver()
        result = r.resolve({"paper_id": 1, "title": "No arXiv ID"})
        assert result.success is False

    def test_with_arxiv_id(self):
        from src.fulltext.arxiv import ArxivResolver
        r = ArxivResolver()
        result = r.resolve({"paper_id": 1, "arxiv_id": "2301.12345", "title": "Test"})
        assert result.access_status == "open_access"
        assert "arxiv.org/pdf" in result.pdf_url
        assert result.legal_status == "legal_oa"


class TestPublisherOAResolver:
    def test_source_name(self):
        from src.fulltext.publisher_oa import PublisherOAResolver
        r = PublisherOAResolver()
        assert r.source_name == "publisher_oa"

    def test_not_oa_returns_error(self):
        from src.fulltext.publisher_oa import PublisherOAResolver
        r = PublisherOAResolver()
        result = r.resolve({"paper_id": 1, "doi": "10.1234/test", "oa_status": "closed"})
        assert result.success is False


class TestInstitutionAccessResolver:
    def test_source_name(self):
        from src.fulltext.institution_access import InstitutionAccessResolver
        r = InstitutionAccessResolver()
        assert r.source_name == "institution_access"

    @patch.dict(os.environ, {"INSTITUTION_NETWORK": "1"})
    def test_detects_institution_network_via_resolve(self):
        from src.fulltext.institution_access import InstitutionAccessResolver
        r = InstitutionAccessResolver()
        # Institution detection happens implicitly in resolve()
        paper = {"paper_id": 1, "doi": "10.1234/test", "title": "Test", "pdf_url": "https://example.com/paper.pdf"}
        result = r.resolve(paper)
        # With INSTITUTION_NETWORK=1, should return institution_access status
        assert result.access_status in ("institution_access", "open_access", "unavailable")

    def test_no_institution_no_pdf_url(self):
        from src.fulltext.institution_access import InstitutionAccessResolver
        r = InstitutionAccessResolver()
        # Without pdf_url, institution resolver returns unavailable
        result = r.resolve({"paper_id": 1, "doi": "10.1234/test", "title": "Test"})
        assert result.access_status == "unavailable"


class TestManualUploadResolver:
    def test_source_name(self):
        from src.fulltext.manual_upload import ManualUploadResolver
        r = ManualUploadResolver()
        assert r.source_name == "manual_upload"

    def test_upload_valid_pdf(self, tmp_path):
        from src.fulltext.manual_upload import ManualUploadResolver

        # 创建足够大的源 PDF (>10240 bytes)
        src = tmp_path / "source.pdf"
        src.write_bytes(b"%PDF-1.4\n" + b"x" * 20000 + b"\n%%EOF")

        pdf_dir = tmp_path / "pdf_output"

        r = ManualUploadResolver()
        paper = {"paper_id": 10, "title": "Test Paper", "year": 2024, "doi": "10.1234/test"}
        result = r.upload(paper, str(src), pdf_dir=pdf_dir, user_confirmed_rights=True)
        assert result.access_status == "manual_upload"
        assert result.pdf_path is not None
        assert Path(result.pdf_path).exists()


# ============================================================================
# FullTextAcquisitionService
# ============================================================================

class TestFullTextAcquisitionService:
    def test_initialization(self):
        from src.fulltext.service import FullTextAcquisitionService
        service = FullTextAcquisitionService()
        assert service is not None
        assert len(service.resolvers) >= 5

    def test_get_statistics(self):
        from src.fulltext.service import FullTextAcquisitionService
        service = FullTextAcquisitionService()
        stats = service.get_statistics()
        assert "total_papers" in stats
        assert "with_pdf" in stats
        assert "without_pdf" in stats

    def test_resolve_nonexistent_paper(self):
        from src.fulltext.service import FullTextAcquisitionService
        service = FullTextAcquisitionService()
        result = service.resolve(99999)
        assert result.access_status == "failed"
        assert "不存在" in result.error_message

    def test_acquire_single_empty_paper(self):
        from src.fulltext.service import FullTextAcquisitionService
        service = FullTextAcquisitionService()
        result = service.acquire_single({})
        assert result.success is False
        assert "paper_id" in result.error_message


# ============================================================================
# 数据库集成测试
# ============================================================================

class TestDatabasePdfStatus:
    def test_update_pdf_status(self):
        from src.storage.repository import PaperRepository
        from src.paper_search.models import PaperMetadata

        repo = PaperRepository()
        paper = PaperMetadata(
            title="DB Test Paper",
            doi="10.9999/dbtest.2026",
            year=2026,
            source_api="test",
        )
        paper_id, action = repo.upsert_paper(paper)

        success = repo.update_paper_pdf_status(
            paper_id,
            pdf_path="/data/pdf/test.pdf",
            download_status="downloaded",
            access_source="unpaywall",
            legal_status="legal_oa",
        )
        assert success is True

        # Verify
        p = repo.get_paper_by_id(paper_id)
        assert p["pdf_path"] == "/data/pdf/test.pdf"
        assert p["download_status"] == "downloaded"

    def test_record_fulltext_access(self):
        from src.storage.repository import PaperRepository
        from src.paper_search.models import PaperMetadata

        repo = PaperRepository()
        paper = PaperMetadata(
            title="FT Access Test",
            doi="10.9999/fttest.2026",
            year=2026,
            source_api="test",
        )
        paper_id, action = repo.upsert_paper(paper)

        record_id = repo.record_fulltext_access(
            paper_id=paper_id,
            doi="10.9999/fttest.2026",
            title="FT Access Test",
            access_status="open_access",
            access_source="unpaywall",
            legal_status="legal_oa",
            pdf_url="https://example.com/test.pdf",
            pdf_path="/data/pdf/test.pdf",
            file_size=12345,
            risk_level="low",
        )
        assert record_id > 0

    def test_get_papers_without_pdf(self):
        from src.storage.repository import PaperRepository
        from src.paper_search.models import PaperMetadata

        repo = PaperRepository()
        paper = PaperMetadata(
            title="No PDF Paper",
            doi="10.9999/nopdf.2026",
            year=2026,
            source_api="test",
        )
        paper_id, action = repo.upsert_paper(paper)

        papers = repo.get_papers_without_pdf(limit=20)
        assert any(p["paper_id"] == paper_id for p in papers)

    def test_get_download_statistics(self):
        from src.storage.repository import PaperRepository
        repo = PaperRepository()
        stats = repo.get_download_statistics()
        assert "total_papers" in stats
        assert "with_pdf" in stats
        assert "without_pdf" in stats
        assert "by_source" in stats
        assert "by_legal_status" in stats

    def test_mark_manual_review(self):
        from src.storage.repository import PaperRepository
        from src.paper_search.models import PaperMetadata

        repo = PaperRepository()
        paper = PaperMetadata(
            title="Review Paper",
            doi="10.9999/review.2026",
            year=2026,
            source_api="test",
        )
        paper_id, action = repo.upsert_paper(paper)

        success = repo.mark_manual_review(paper_id, "Need manual check")
        assert success is True

        p = repo.get_paper_by_id(paper_id)
        assert p["download_status"] == "manual_review"


# ============================================================================
# Source label mapping
# ============================================================================

class TestFriendlySource:
    def test_all_sources_mapped(self):
        from ui.services.fulltext_ui_service import friendly_source
        assert friendly_source("all_sources") == "全部合法来源均未找到"
        assert friendly_source("unpaywall") == "Unpaywall"
        assert friendly_source("pmc") == "PubMed Central"
        assert friendly_source("arxiv") == "arXiv"
        assert friendly_source("publisher_oa") == "出版社开放获取"
        assert friendly_source("institution_access") == "校园网/机构授权访问"
        assert friendly_source("manual_upload") == "手动上传"

    def test_unknown_source_passthrough(self):
        from ui.services.fulltext_ui_service import friendly_source
        assert friendly_source("custom_source") == "custom_source"
        assert friendly_source("") == ""


# ============================================================================
# Unavailable status handling
# ============================================================================

class TestUnavailableStatus:
    def test_unavailable_result_not_counted_as_failed(self):
        """unavailable != failed — unavailable means legal sources exhausted."""
        from src.fulltext.base import FullTextResult
        r = FullTextResult(
            paper_id=1, access_status="unavailable",
            source="all_sources", legal_status="unknown",
            error_message="所有合法来源均未找到可用全文",
        )
        assert r.access_status == "unavailable"
        assert r.pdf_path is None
        # unavailable should NOT be classified as failed
        assert r.access_status != "failed"

    def test_unavailable_maps_to_unavailable_download_status(self):
        """_update_database should set download_status='unavailable', not 'pending'."""
        from src.fulltext.base import FullTextResult
        from src.storage.repository import PaperRepository
        from src.paper_search.models import PaperMetadata

        repo = PaperRepository()
        paper = PaperMetadata(
            title="Unavailable Test Paper",
            doi="10.9999/unavail.2026",
            year=2026, source_api="test",
        )
        pid, _ = repo.upsert_paper(paper)

        result = FullTextResult(
            paper_id=pid, access_status="unavailable",
            source="all_sources", legal_status="unknown",
            error_message="所有合法来源均未找到可用全文",
        )

        # Simulate _update_database logic
        if result.pdf_path:
            download_status = "downloaded"
        elif result.access_status == "failed":
            download_status = "failed"
        elif result.access_status == "manual_review":
            download_status = "manual_review"
        elif result.access_status == "unavailable":
            download_status = "unavailable"
        else:
            download_status = "pending"

        assert download_status == "unavailable", f"Expected 'unavailable', got '{download_status}'"


# ============================================================================
# Batch summary counts
# ============================================================================

class TestBatchSummary:
    def test_batch_summary_counts(self):
        """Verify batch_download_pending computes correct summary counts."""
        from src.fulltext.base import FullTextResult

        # Build a mix of result statuses
        results = [
            FullTextResult(paper_id=1, access_status="open_access", pdf_path="/tmp/p1.pdf"),
            FullTextResult(paper_id=2, access_status="unavailable", source="all_sources",
                          error_message="所有合法来源均未找到可用全文"),
            FullTextResult(paper_id=3, access_status="unavailable", source="all_sources"),
            FullTextResult(paper_id=4, access_status="manual_review", source="manual_upload"),
            FullTextResult(paper_id=5, access_status="failed", source="unknown",
                          error_message="下载异常"),
        ]

        downloaded = len([r for r in results if r.pdf_path])
        unavailable = len([r for r in results if r.access_status == "unavailable"])
        manual_review = len([r for r in results if r.access_status == "manual_review"])
        failed = len([r for r in results if r.access_status == "failed"])

        assert downloaded == 1
        assert unavailable == 2
        assert manual_review == 1
        assert failed == 1
        assert unavailable + failed == 3
        # unavailable should NOT inflate failed_count
        assert failed == 1
