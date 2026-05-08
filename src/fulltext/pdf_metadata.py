"""Extract DOI, title, year, authors from PDF text using PyMuPDF."""

import re
from pathlib import Path

import fitz

from src.utils.logger import get_logger

_log = get_logger(__name__)

_DOI_RE = re.compile(r"\b10\.\d{4,}/[^\s]+\b")
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def extract_metadata(pdf_path: Path, max_pages: int = 3) -> dict:
    """Return {doi, title, year, authors, page_count} from a PDF."""
    result = {"doi": "", "title": "", "year": None, "authors": "", "page_count": 0}

    try:
        doc = fitz.open(str(pdf_path))
    except Exception:
        return result

    result["page_count"] = doc.page_count
    pages_to_read = min(max_pages, doc.page_count)

    all_text = ""
    for i in range(pages_to_read):
        all_text += doc[i].get_text("text") + "\n"

    doc.close()

    lines = [l.strip() for l in all_text.splitlines() if l.strip()]

    # DOI
    doi_match = _DOI_RE.search(all_text)
    if doi_match:
        result["doi"] = doi_match.group(0).rstrip(".,;")

    # Title: first substantial line
    for line in lines[:10]:
        if len(line) > 15 and not line.startswith(("©", "http", "DOI", "doi:")):
            result["title"] = line[:300]
            break

    # Year
    year_match = _YEAR_RE.search(all_text)
    if year_match:
        y = int(year_match.group(0))
        if 1900 < y < 2030:
            result["year"] = y

    _log.info("Extracted from %s: doi=%s title=%s...", pdf_path.name,
              result["doi"], result["title"][:50])

    return result
