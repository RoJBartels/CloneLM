"""Plain-text / HTML / PDF extraction.

Each extractor returns an ``ExtractedText``: the full concatenated text (the
char-offset space chunking will index into) plus optional page boundaries so
chunks can be stamped with a page number for citations.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field

from bs4 import BeautifulSoup
from pypdf import PdfReader

from app.shared.errors import UnsupportedSourceError


@dataclass
class ExtractedText:
    """``text`` is the full extracted document. ``page_breaks`` (PDF only) is a
    list of ``(start_char, end_char, page_number)`` tuples covering ``text`` so
    the chunker can look up which page a char offset falls in."""

    text: str
    page_breaks: list[tuple[int, int, int]] = field(default_factory=list)

    def page_at(self, char_offset: int) -> int | None:
        for start, end, page in self.page_breaks:
            if start <= char_offset < end:
                return page
        return None


def extract_plain_text(raw: bytes | str) -> ExtractedText:
    """txt/md passthrough — decode as utf-8 if given bytes."""
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
    return ExtractedText(text=text)


def extract_html(html: str) -> ExtractedText:
    """HTML -> text: strip script/style, collapse whitespace."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    raw_text = soup.get_text(separator=" ")
    collapsed = " ".join(raw_text.split())
    return ExtractedText(text=collapsed)


def extract_pdf(raw: bytes) -> ExtractedText:
    """Extract text per page via pypdf, concatenating with page boundaries
    tracked so chunks can be stamped with a page number."""
    try:
        reader = PdfReader(io.BytesIO(raw))
    except Exception as exc:  # pragma: no cover - depends on malformed input
        raise UnsupportedSourceError(f"Could not read PDF: {exc}") from exc

    parts: list[str] = []
    page_breaks: list[tuple[int, int, int]] = []
    cursor = 0
    for page_number, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        if parts:
            parts.append("\n")
            cursor += 1
        start = cursor
        parts.append(page_text)
        cursor += len(page_text)
        page_breaks.append((start, cursor, page_number))

    return ExtractedText(text="".join(parts), page_breaks=page_breaks)
