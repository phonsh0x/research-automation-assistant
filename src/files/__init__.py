"""Unified file path handling for the research-automation-assistant."""

from src.files.path_resolver import (
    get_project_root,
    resolve_project_path,
    to_relative_path,
    to_portable_path,
    ensure_directory,
    is_file_valid,
    is_pdf_file,
    is_markdown_file,
    file_status,
    pdf_status,
    markdown_status,
    safe_filename,
    build_pdf_storage_path,
    build_markdown_storage_path,
    build_upload_stage_path,
)

__all__ = [
    "get_project_root",
    "resolve_project_path",
    "to_relative_path",
    "to_portable_path",
    "ensure_directory",
    "is_file_valid",
    "is_pdf_file",
    "is_markdown_file",
    "file_status",
    "pdf_status",
    "markdown_status",
    "safe_filename",
    "build_pdf_storage_path",
    "build_markdown_storage_path",
    "build_upload_stage_path",
]
