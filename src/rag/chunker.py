"""Markdown document chunker for RAG ingestion.

Splits academic Markdown into overlapping, section-aware chunks suitable
for embedding and retrieval.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.utils.logger import get_logger

_log = get_logger(__name__)

# Matches ATX headings (1-6 #) with optional trailing #s
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)(?:\s+#+\s*)?$", re.MULTILINE)


@dataclass
class MarkdownChunk:
    """A single chunk of Markdown text ready for embedding."""

    paper_id: int | None = None
    chunk_index: int = 0
    text: str = ""
    section: str = ""
    title: str | None = None
    source_path: str | None = None
    char_count: int = 0
    word_count: int = 0
    metadata: dict = field(default_factory=dict)


class MarkdownChunker:
    """Split Markdown into overlapping, section-aware chunks."""

    def __init__(self, max_chars: int = 2000, overlap_chars: int = 200,
                 min_chars: int = 100):
        if max_chars <= 0:
            raise ValueError("max_chars must be > 0")
        if overlap_chars < 0:
            raise ValueError("overlap_chars must be >= 0")
        if overlap_chars >= max_chars:
            raise ValueError("overlap_chars must be < max_chars")
        if min_chars < 0:
            raise ValueError("min_chars must be >= 0")

        self.max_chars = max_chars
        self.overlap_chars = overlap_chars
        self.min_chars = min_chars

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chunk_text(self, markdown: str, paper_id: int | None = None,
                   title: str | None = None,
                   source_path: str | None = None) -> list[MarkdownChunk]:
        """Split *markdown* text into chunks."""
        if not markdown or not markdown.strip():
            return []

        sections = self._split_sections(markdown)
        chunks = self._chunk_sections(sections, paper_id, title, source_path)
        return chunks

    def chunk_file(self, path: str | Path, paper_id: int | None = None,
                   title: str | None = None) -> list[MarkdownChunk]:
        """Read a Markdown file and chunk its contents."""
        md_text = Path(path).read_text(encoding="utf-8")
        return self.chunk_text(md_text, paper_id=paper_id, title=title,
                               source_path=str(path))

    # ------------------------------------------------------------------
    # Section splitting
    # ------------------------------------------------------------------

    @staticmethod
    def _split_sections(markdown: str) -> list[dict]:
        """Split markdown into a list of {'heading': str, 'level': int,
        'text': str} dicts.

        Text before the first heading is placed in a section with
        heading ``"正文"`` and level 0.
        """
        matches = list(_HEADING_RE.finditer(markdown))
        if not matches:
            return [{"heading": "正文", "level": 0, "text": markdown.strip()}]

        sections = []
        # Preamble before first heading
        if matches[0].start() > 0:
            preamble = markdown[:matches[0].start()].strip()
            if preamble:
                sections.append({"heading": "正文", "level": 0, "text": preamble})

        for i, m in enumerate(matches):
            level = len(m.group(1))
            heading = m.group(2).strip()
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
            text = markdown[start:end].strip()
            if text:
                sections.append({"heading": heading, "level": level, "text": text})

        return sections

    # ------------------------------------------------------------------
    # Chunking
    # ------------------------------------------------------------------

    def _chunk_sections(self, sections: list[dict], paper_id: int | None,
                        title: str | None,
                        source_path: str | None) -> list[MarkdownChunk]:
        """Produce chunks from sections, assigning incremental indices."""
        chunks: list[MarkdownChunk] = []
        idx = 0

        for si, sec in enumerate(sections):
            heading = sec["heading"]
            level = sec["level"]
            paragraphs = _split_paragraphs(sec["text"])

            # Combine paragraphs into max_chars chunks
            sec_chunks = _combine_paragraphs(
                paragraphs, self.max_chars, self.min_chars,
                self.overlap_chars,
            )
            for text in sec_chunks:
                chunks.append(MarkdownChunk(
                    paper_id=paper_id,
                    chunk_index=idx,
                    text=text,
                    section=heading,
                    title=title,
                    source_path=source_path,
                    char_count=len(text),
                    word_count=len(text.split()),
                    metadata={
                        "heading_level": level,
                        "section_index": si,
                        "source_path": source_path or "",
                    },
                ))
                idx += 1

        return chunks


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------

def _split_paragraphs(text: str) -> list[str]:
    """Split text into non-empty paragraphs (double-newline boundaries)."""
    raw = re.split(r"\n\s*\n", text)
    return [p.strip() for p in raw if p.strip()]


def _combine_paragraphs(paragraphs: list[str], max_chars: int,
                        min_chars: int, overlap_chars: int) -> list[str]:
    """Combine paragraphs into chunks respecting *max_chars*.

    Each chunk contains one or more paragraphs.  When a single paragraph
    exceeds *max_chars* it is hard-split via ``_hard_split``.
    *overlap_chars* only applies inside ``_hard_split`` — regular
    paragraph combination does not add overlap, so chunks stay within
    *max_chars*.

    When the final chunk is shorter than *min_chars* and can be merged
    with the preceding chunk without exceeding *max_chars*, the two are
    joined.  Hard-split tail chunks are exempt from this check.
    """
    if not paragraphs:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    def _flush() -> str | None:
        nonlocal current, current_len
        if not current:
            return None
        body = "\n\n".join(current)
        current = []
        current_len = 0
        return body

    for p in paragraphs:
        p_len = len(p) + (2 if current else 0)  # account for "\n\n" separator

        # If a single paragraph exceeds max_chars, flush current buffer
        # first, then hard-split the long paragraph.
        if p_len > max_chars and not current:
            sub_chunks = _hard_split(p, max_chars, overlap_chars)
            for sc in sub_chunks:
                chunks.append(sc)
            continue

        if p_len > max_chars:
            body = _flush()
            if body:
                chunks.append(body)
            sub_chunks = _hard_split(p, max_chars, overlap_chars)
            for sc in sub_chunks:
                chunks.append(sc)
            continue

        if current_len + p_len <= max_chars:
            current.append(p)
            current_len += p_len
        else:
            body = _flush()
            if body:
                chunks.append(body)
            current.append(p)
            current_len = len(p)

    # Final flush
    body = _flush()
    if body:
        chunks.append(body)

    # Merge short tail chunk into previous if possible.
    # Only applies when at least 2 chunks exist and the tail was produced
    # by paragraph combination (not hard-split, which always uses max_chars).
    if min_chars > 0 and len(chunks) >= 2:
        last_len = len(chunks[-1])
        if last_len < min_chars:
            combined = chunks[-2] + "\n\n" + chunks[-1]
            if len(combined) <= max_chars:
                chunks[-2] = combined
                chunks.pop()

    return chunks


def _hard_split(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    """Hard-split a single long paragraph into *max_chars* chunks with
    optional overlap.

    Overlap is implemented by taking the last *overlap_chars* characters
    of the previous chunk and prepending them to the next.  The overlap
    is only added when it does not produce an empty chunk and does not
    cause an infinite loop (i.e. overlap_chars < max_chars is validated
    in the constructor).
    """
    parts: list[str] = []
    start = 0
    n = len(text)

    while start < n:
        end = min(start + max_chars, n)
        parts.append(text[start:end])
        if end >= n:
            break
        # Advance start, accounting for overlap
        step = max_chars - overlap_chars
        if step <= 0:
            # Safety: should never happen (validated in __init__)
            step = 1
        start += step

    return parts
