"""Unified file path resolution for the research-automation-assistant.

All path construction funnels through this module so that relative/absolute
handling, illegal-char sanitisation, and overwrite avoidance are consistent
across the codebase.

Reuses ``src.config.PROJECT_ROOT`` as the single source of truth for the
project root directory.
"""

import re
import uuid
from datetime import datetime
from pathlib import Path

from src.config import PROJECT_ROOT, get_data_path
from src.utils.logger import get_logger

_log = get_logger(__name__)

# Characters illegal in Windows file names
_ILLEGAL_CHARS_RE = re.compile(r'[\\/:*?"<>|]')

# Characters we strip from start/end of safe filenames
_TRIM_CHARS_RE = re.compile(r"^[.\s]+|[.\s]+$")


# ---------------------------------------------------------------------------
# Project root
# ---------------------------------------------------------------------------


def get_project_root() -> Path:
    """Return the absolute project root directory.

    Delegates to ``src.config.PROJECT_ROOT`` so there is exactly one
    definition regardless of how many modules need it.
    """
    return PROJECT_ROOT


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def resolve_project_path(path: str | Path) -> Path:
    """Resolve *path* to an absolute Path under the project root.

    - Absolute paths are returned unchanged (no existence check).
    - Relative paths are joined against ``get_project_root()``.
    """
    p = Path(path)
    if p.is_absolute():
        return p
    return get_project_root() / p


def to_relative_path(path: str | Path) -> str:
    """Convert *path* to a project-relative string with forward slashes.

    - If *path* is under the project root the returned string does **not**
      include the project-root prefix.
    - If *path* is already relative it is normalised to ``/`` separators.
    - Absolute paths outside the project root are normalised but kept
      absolute.
    """
    p = Path(path)
    try:
        rel = p.resolve().relative_to(get_project_root().resolve())
        return rel.as_posix()
    except ValueError:
        # Not under project root — normalise slashes
        return p.as_posix()


def to_portable_path(path: str | Path) -> str:
    """Return a database-safe portable path.

    Prefers a project-relative path with forward slashes.  Absolute paths
    that sit under the project root are trimmed so the stored value does
    not embed a machine-specific prefix.
    """
    p = Path(path)
    if not p.is_absolute():
        return p.as_posix()
    return to_relative_path(p)


# ---------------------------------------------------------------------------
# Directory helpers
# ---------------------------------------------------------------------------


def ensure_directory(path: str | Path) -> Path:
    """Resolve *path* to an absolute directory, creating it if needed."""
    p = resolve_project_path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# File validation
# ---------------------------------------------------------------------------


def is_file_valid(path: str | Path, expected_suffix: str | None = None) -> bool:
    """Return ``True`` when *path* exists, is a non-empty file, and
    optionally matches *expected_suffix* (case-insensitive)."""
    p = Path(path)
    if not p.is_file():
        return False
    if p.stat().st_size == 0:
        return False
    if expected_suffix is not None:
        if p.suffix.lower() != expected_suffix.lower():
            return False
    return True


def is_pdf_file(path: str | Path) -> bool:
    """``is_file_valid(path, '.pdf')``"""
    return is_file_valid(path, ".pdf")


def is_markdown_file(path: str | Path) -> bool:
    """``is_file_valid(path, '.md')``"""
    return is_file_valid(path, ".md")


# ---------------------------------------------------------------------------
# Human-readable status
# ---------------------------------------------------------------------------


def file_status(path: str | Path | None,
                expected_suffix: str | None = None) -> tuple[bool, str]:
    """Return ``(ok, label)`` for user-facing file-status display.

    Labels are Chinese strings suitable for direct UI use.
    """
    if not path:
        return False, "路径缺失"
    p = Path(path)
    if not p.exists():
        return False, "文件不存在"
    if not p.is_file():
        return False, "不是文件"
    if p.stat().st_size == 0:
        return False, "文件为空"
    if expected_suffix is not None:
        if p.suffix.lower() != expected_suffix.lower():
            return False, "格式异常"
    return True, "已存在"


def pdf_status(path: str | Path | None) -> tuple[bool, str]:
    """``file_status(path, '.pdf')``"""
    return file_status(path, ".pdf")


def markdown_status(path: str | Path | None) -> tuple[bool, str]:
    """``file_status(path, '.md')``"""
    return file_status(path, ".md")


# ---------------------------------------------------------------------------
# Safe file-name construction
# ---------------------------------------------------------------------------


def safe_filename(name: str, max_length: int = 120, fallback: str = "untitled") -> str:
    """Return a filesystem-safe filename derived from *name*.

    - Replaces Windows-illegal characters (``\\/:*?"<>|``) with ``_``.
    - Collapses consecutive underscores and whitespace.
    - Strips leading/trailing dots, spaces and underscores.
    - If the result is empty or starts with a dot, returns *fallback*.
    - Truncates to *max_length* characters, preserving the extension when
      the truncation falls inside the stem.
    """
    cleaned = _ILLEGAL_CHARS_RE.sub("_", name)
    cleaned = re.sub(r"_+", "_", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = _TRIM_CHARS_RE.sub("", cleaned)

    if not cleaned or cleaned.startswith("."):
        return fallback

    if len(cleaned) > max_length:
        # Try to keep extension
        suffix = Path(cleaned).suffix
        stem = Path(cleaned).stem
        if suffix and len(stem) > 3:
            avail = max_length - len(suffix)
            if avail > 3:
                cleaned = stem[:avail] + suffix
            else:
                cleaned = cleaned[:max_length]
        else:
            cleaned = cleaned[:max_length]
        cleaned = _TRIM_CHARS_RE.sub("", cleaned)

    return cleaned or fallback


# ---------------------------------------------------------------------------
# Storage-path builders
# ---------------------------------------------------------------------------


def _avoid_overwrite(dir_path: Path, stem: str, suffix: str) -> Path:
    """Return ``dir_path / (stem + suffix)``, appending a short unique
    token when a file with that name already exists."""
    candidate = dir_path / (stem + suffix)
    if not candidate.exists():
        return candidate
    # Append a short timestamp to disambiguate
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    dedup = dir_path / f"{stem}_{ts}{suffix}"
    if dedup.exists():
        dedup = dir_path / f"{stem}_{ts}_{uuid.uuid4().hex[:6]}{suffix}"
    return dedup


def build_pdf_storage_path(title: str, doi: str = "", year: int | None = None,
                           avoid_overwrite: bool = True) -> Path:
    """Build an absolute path under ``data/pdf/`` for a PDF.

    The filename is derived from *year*, *doi* and *title*.  When
    *avoid_overwrite* is ``True`` a short timestamp is appended when a
    file with the same name already exists.
    """
    pdf_dir = get_data_path("data/pdf")
    parts = []
    if year:
        parts.append(str(year))
    if doi:
        # Extract the last segment of the DOI as a short identifier
        doi_part = doi.split("/")[-1] if "/" in doi else doi
        parts.append(safe_filename(doi_part, max_length=40))
    title_part = safe_filename(title, max_length=80)
    parts.append(title_part)
    stem = "_".join(parts) if parts else "paper"
    stem = safe_filename(stem, max_length=180)

    if avoid_overwrite:
        return _avoid_overwrite(pdf_dir, stem, ".pdf")
    return pdf_dir / (stem + ".pdf")


def build_markdown_storage_path(title: str, paper_id: int | None = None,
                                avoid_overwrite: bool = True) -> Path:
    """Build an absolute path under ``data/markdown/`` for a Markdown file.

    The filename uses *title*.  *paper_id* is only added as a
    disambiguation suffix when *avoid_overwrite* would otherwise cause a
    collision — it never appears in the primary filename.
    """
    md_dir = get_data_path("data/markdown")
    stem = safe_filename(title, max_length=120)
    if not stem or stem == "untitled":
        stem = f"paper_{paper_id}" if paper_id else "converted_paper"

    if avoid_overwrite:
        return _avoid_overwrite(md_dir, stem, ".md")
    return md_dir / (stem + ".md")


def build_upload_stage_path(original_filename: str) -> Path:
    """Build an absolute path under ``temp/paper_uploads/`` for a staged
    upload, avoiding name collisions."""
    stage_dir = get_data_path("temp/paper_uploads")
    stem = safe_filename(original_filename, max_length=120)
    if not stem:
        stem = "upload"
    return _avoid_overwrite(stage_dir, stem, "")
