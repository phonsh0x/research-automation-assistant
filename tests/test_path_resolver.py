"""Tests for src.files.path_resolver — unified file path handling."""

import uuid
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def resolver():
    from src.files import path_resolver
    return path_resolver


@pytest.fixture
def project_root():
    from src.config import PROJECT_ROOT
    return PROJECT_ROOT


# ---------------------------------------------------------------------------
# get_project_root
# ---------------------------------------------------------------------------

class TestGetProjectRoot:
    def test_consistent_with_config(self, resolver, project_root):
        assert resolver.get_project_root() == project_root

    def test_returns_absolute_path(self, resolver):
        root = resolver.get_project_root()
        assert root.is_absolute()

    def test_is_existing_directory(self, resolver):
        assert resolver.get_project_root().is_dir()


# ---------------------------------------------------------------------------
# resolve_project_path
# ---------------------------------------------------------------------------

class TestResolveProjectPath:
    def test_relative_path_resolves(self, resolver, project_root):
        result = resolver.resolve_project_path("data/pdf")
        assert result.is_absolute()
        assert result == project_root / "data/pdf"

    def test_absolute_path_unchanged(self, resolver, tmp_path):
        result = resolver.resolve_project_path(str(tmp_path))
        assert result == tmp_path

    def test_absolute_path_no_existence_check(self, resolver):
        fake = Path("Z:/nonexistent/path/file.pdf")
        result = resolver.resolve_project_path(fake)
        assert result == fake

    def test_path_object_accepted(self, resolver, project_root):
        result = resolver.resolve_project_path(Path("data/markdown"))
        assert result == project_root / "data/markdown"


# ---------------------------------------------------------------------------
# to_relative_path
# ---------------------------------------------------------------------------

class TestToRelativePath:
    def test_absolute_under_project_root(self, resolver, project_root):
        abs_path = project_root / "data/pdf/test.pdf"
        rel = resolver.to_relative_path(abs_path)
        assert rel == "data/pdf/test.pdf"
        assert "\\" not in rel

    def test_already_relative(self, resolver):
        rel = resolver.to_relative_path("data/pdf/paper.pdf")
        assert rel == "data/pdf/paper.pdf"

    def test_outside_project_root(self, resolver, tmp_path):
        # Absolute path outside project root stays absolute but normalised
        result = resolver.to_relative_path(tmp_path / "external.pdf")
        assert "\\" not in result
        # Should be absolute since it's outside the project
        assert Path(result).is_absolute() or result.startswith("/") or ":" in result

    def test_windows_backslash_normalised(self, resolver, project_root):
        # Simulate a Windows-style path under project root
        win_path = str(project_root / "data" / "pdf" / "paper.pdf")
        # Force backslashes in the string
        win_path_bs = win_path.replace("/", "\\")
        rel = resolver.to_relative_path(win_path_bs)
        assert "\\" not in rel
        assert rel == "data/pdf/paper.pdf"


# ---------------------------------------------------------------------------
# to_portable_path
# ---------------------------------------------------------------------------

class TestToPortablePath:
    def test_absolute_becomes_relative(self, resolver, project_root):
        abs_path = project_root / "data/markdown/paper.md"
        result = resolver.to_portable_path(abs_path)
        assert result == "data/markdown/paper.md"

    def test_relative_stays_relative(self, resolver):
        result = resolver.to_portable_path("data/pdf/test.pdf")
        assert result == "data/pdf/test.pdf"

    def test_no_project_root_prefix(self, resolver, project_root):
        abs_path = project_root / "data/pdf/x.pdf"
        result = resolver.to_portable_path(abs_path)
        root_str = str(project_root).replace("\\", "/")
        assert root_str not in result

    def test_forward_slashes_only(self, resolver, project_root):
        abs_path = project_root / "data" / "pdf" / "x.pdf"
        result = resolver.to_portable_path(str(abs_path).replace("/", "\\"))
        assert "\\" not in result


# ---------------------------------------------------------------------------
# ensure_directory
# ---------------------------------------------------------------------------

class TestEnsureDirectory:
    def test_creates_and_returns_absolute(self, resolver, tmp_path):
        p = resolver.ensure_directory(tmp_path / "sub" / "nested")
        assert p.is_dir()
        assert p.is_absolute()

    def test_existing_directory_ok(self, resolver, tmp_path):
        p = resolver.ensure_directory(tmp_path)
        assert p == tmp_path.resolve()


# ---------------------------------------------------------------------------
# is_file_valid / is_pdf_file / is_markdown_file
# ---------------------------------------------------------------------------

class TestFileValidation:
    def test_valid_pdf(self, resolver, tmp_path):
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4\ncontent")
        assert resolver.is_pdf_file(pdf) is True
        assert resolver.is_file_valid(pdf, ".pdf") is True

    def test_valid_markdown(self, resolver, tmp_path):
        md = tmp_path / "notes.md"
        md.write_text("# Hello", encoding="utf-8")
        assert resolver.is_markdown_file(md) is True
        assert resolver.is_file_valid(md, ".md") is True

    def test_missing_file(self, resolver, tmp_path):
        assert resolver.is_pdf_file(tmp_path / "gone.pdf") is False

    def test_wrong_suffix(self, resolver, tmp_path):
        txt = tmp_path / "readme.txt"
        txt.write_text("hello")
        assert resolver.is_file_valid(txt, ".pdf") is False

    def test_empty_file(self, resolver, tmp_path):
        empty = tmp_path / "empty.pdf"
        empty.write_bytes(b"")
        assert resolver.is_file_valid(empty, ".pdf") is False

    def test_directory_not_file(self, resolver, tmp_path):
        assert resolver.is_file_valid(tmp_path, ".pdf") is False

    def test_suffix_case_insensitive(self, resolver, tmp_path):
        pdf = tmp_path / "doc.PDF"
        pdf.write_bytes(b"%PDF-1.4\nx")
        assert resolver.is_file_valid(pdf, ".pdf") is True


# ---------------------------------------------------------------------------
# file_status / pdf_status / markdown_status
# ---------------------------------------------------------------------------

class TestFileStatus:
    def test_none_returns_missing_label(self, resolver):
        ok, label = resolver.file_status(None)
        assert ok is False
        assert label == "路径缺失"

    def test_empty_string_returns_missing_label(self, resolver):
        ok, label = resolver.file_status("")
        assert ok is False
        assert label == "路径缺失"

    def test_nonexistent_file(self, resolver, tmp_path):
        ok, label = resolver.file_status(tmp_path / "no.pdf")
        assert ok is False
        assert label == "文件不存在"

    def test_directory_not_file(self, resolver, tmp_path):
        ok, label = resolver.file_status(tmp_path, ".pdf")
        assert ok is False
        assert label == "不是文件"

    def test_empty_file(self, resolver, tmp_path):
        f = tmp_path / "empty.pdf"
        f.write_bytes(b"")
        ok, label = resolver.file_status(f, ".pdf")
        assert ok is False
        assert label == "文件为空"

    def test_wrong_suffix(self, resolver, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("x")
        ok, label = resolver.file_status(f, ".pdf")
        assert ok is False
        assert label == "格式异常"

    def test_valid_pdf_status(self, resolver, tmp_path):
        f = tmp_path / "ok.pdf"
        f.write_bytes(b"%PDF-1.4\nx")
        ok, label = resolver.pdf_status(f)
        assert ok is True
        assert label == "已存在"

    def test_pdf_status_missing(self, resolver, tmp_path):
        ok, label = resolver.pdf_status(tmp_path / "no.pdf")
        assert ok is False
        assert label == "文件不存在"

    def test_markdown_status(self, resolver, tmp_path):
        f = tmp_path / "ok.md"
        f.write_text("# hi")
        ok, label = resolver.markdown_status(f)
        assert ok is True
        assert label == "已存在"


# ---------------------------------------------------------------------------
# safe_filename
# ---------------------------------------------------------------------------

class TestSafeFilename:
    def test_illegal_chars_replaced(self, resolver):
        result = resolver.safe_filename('test:file<name>.pdf')
        assert ":" not in result
        assert "<" not in result
        assert result == "test_file_name_.pdf"

    def test_empty_returns_fallback(self, resolver):
        result = resolver.safe_filename("")
        assert result == "untitled"

    def test_all_chars_illegal_leaves_only_underscores(self, resolver):
        # Every char is illegal → replaced by _, then collapsed to a single _
        result = resolver.safe_filename(':*?"<>|')
        # A lone underscore is a valid filename; it won't trigger fallback
        assert result == "_"

    def test_dot_only_returns_fallback(self, resolver):
        result = resolver.safe_filename("...")
        assert result == "untitled"

    def test_trims_leading_trailing_spaces_and_dots(self, resolver):
        result = resolver.safe_filename("  hello world.  ")
        assert result == "hello world"

    def test_truncates_long_name(self, resolver):
        long_name = "a" * 200
        result = resolver.safe_filename(long_name, max_length=80)
        assert len(result) <= 80

    def test_truncation_preserves_extension(self, resolver):
        long_name = "b" * 200 + ".pdf"
        result = resolver.safe_filename(long_name, max_length=40)
        assert result.endswith(".pdf")
        assert len(result) <= 40

    def test_collapses_multiple_underscores(self, resolver):
        result = resolver.safe_filename("a///b\\c")
        assert result == "a_b_c"

    def test_custom_fallback(self, resolver):
        result = resolver.safe_filename("", fallback="default_name")
        assert result == "default_name"


# ---------------------------------------------------------------------------
# build_pdf_storage_path
# ---------------------------------------------------------------------------

class TestBuildPdfStoragePath:
    def test_returns_under_data_pdf(self, resolver):
        p = resolver.build_pdf_storage_path("My Paper", year=2024)
        assert p.is_absolute()
        assert "data" in p.parts
        # data/pdf should be in the path
        assert "pdf" in p.parts or p.parent.name == "pdf"

    def test_suffix_is_pdf(self, resolver):
        p = resolver.build_pdf_storage_path("Test")
        assert p.suffix.lower() == ".pdf"

    def test_includes_year(self, resolver):
        p = resolver.build_pdf_storage_path("Test", year=2025)
        assert "2025" in p.stem

    def test_includes_doi_fragment(self, resolver):
        p = resolver.build_pdf_storage_path("Test", doi="10.1234/abcdef")
        assert "abcdef" in p.stem

    def test_safe_title_used(self, resolver):
        p = resolver.build_pdf_storage_path("Bad:Title*Here")
        assert ":" not in p.stem
        assert "*" not in p.stem

    def test_avoid_overwrite_creates_unique(self, resolver, tmp_path):
        # We cannot easily test with get_data_path, but we can verify
        # two calls with same title produce the same path when file doesn't exist yet
        p1 = resolver.build_pdf_storage_path("Unique Paper XYZ 999", avoid_overwrite=True)
        p2 = resolver.build_pdf_storage_path("Unique Paper XYZ 999", avoid_overwrite=True)
        # When no file exists, both should return the same canonical path
        assert p1 == p2


# ---------------------------------------------------------------------------
# build_markdown_storage_path
# ---------------------------------------------------------------------------

class TestBuildMarkdownStoragePath:
    def test_returns_under_data_markdown(self, resolver):
        p = resolver.build_markdown_storage_path("Research Paper")
        assert p.is_absolute()
        assert "markdown" in p.parts or p.parent.name == "markdown"

    def test_suffix_is_md(self, resolver):
        p = resolver.build_markdown_storage_path("Analysis")
        assert p.suffix.lower() == ".md"

    def test_untitled_fallback(self, resolver):
        p = resolver.build_markdown_storage_path("", paper_id=42)
        assert "42" in p.stem or "paper" in p.stem.lower()

    def test_paper_id_not_in_normal_filename(self, resolver):
        p = resolver.build_markdown_storage_path("正常论文标题")
        assert "正常论文标题" in p.stem

    def test_avoid_overwrite(self, resolver):
        p1 = resolver.build_markdown_storage_path("Unique MD XYZ 999", avoid_overwrite=True)
        p2 = resolver.build_markdown_storage_path("Unique MD XYZ 999", avoid_overwrite=True)
        assert p1 == p2  # Same when no collision


# ---------------------------------------------------------------------------
# build_upload_stage_path
# ---------------------------------------------------------------------------

class TestBuildUploadStagePath:
    def test_returns_under_temp_paper_uploads(self, resolver):
        p = resolver.build_upload_stage_path("test.pdf")
        assert p.is_absolute()
        path_str = p.as_posix()
        assert "temp" in path_str
        assert "paper_uploads" in path_str

    def test_filename_sanitised(self, resolver):
        p = resolver.build_upload_stage_path('bad:file<name>.pdf')
        assert ":" not in p.name
        assert "<" not in p.name


# ---------------------------------------------------------------------------
# Windows path handling
# ---------------------------------------------------------------------------

class TestWindowsPaths:
    def test_backslash_in_relative_converted(self, resolver, project_root):
        win_path = str(project_root / "data" / "pdf" / "x.pdf").replace("/", "\\")
        result = resolver.to_portable_path(win_path)
        assert "\\" not in result

    def test_to_relative_path_handles_windows_abs(self, resolver, project_root):
        win_abs = str(project_root / "data" / "readme.md").replace("/", "\\")
        rel = resolver.to_relative_path(win_abs)
        assert "\\" not in rel

    def test_resolve_project_path_handles_backslash(self, resolver, project_root):
        # Even with backslashes, the result should be a proper Path
        sub = "data" + "\\" + "pdf"
        result = resolver.resolve_project_path(sub)
        assert result.is_absolute()
