"""Source text extraction: turns raw bytes/HTML into plain text (+ optional
per-page boundaries for PDFs) ready for chunking.

Pure parsing logic only — no persistence, no embedding. Depends only on
stdlib + the parsing libraries (pypdf, beautifulsoup4) and ``app.shared``.
"""
from __future__ import annotations

from app.services.ingestion.parsing.extract import (
    ExtractedText,
    extract_html,
    extract_pdf,
    extract_plain_text,
)

__all__ = ["ExtractedText", "extract_html", "extract_pdf", "extract_plain_text"]
