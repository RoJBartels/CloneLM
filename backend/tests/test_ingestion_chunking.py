"""Unit tests for the token-aware chunker. No DB, no embedder — pure logic."""
from __future__ import annotations

from app.services.ingestion.chunking import chunk_text


def test_offsets_round_trip():
    text = "Satz eins. " * 50 + "Satz zwei am Ende."
    spans = chunk_text(text, chunk_tokens=32, chunk_overlap=8)
    assert spans, "expected at least one chunk"
    for span in spans:
        assert text[span.start_char : span.end_char] == span.text


def test_ordinals_sequential():
    text = "Wort " * 500
    spans = chunk_text(text, chunk_tokens=32, chunk_overlap=8)
    assert [s.ordinal for s in spans] == list(range(len(spans)))


def test_overlap_present_between_consecutive_chunks():
    text = "Lorem ipsum dolor sit amet consectetur adipiscing elit. " * 30
    spans = chunk_text(text, chunk_tokens=32, chunk_overlap=8)
    assert len(spans) >= 2
    for a, b in zip(spans, spans[1:]):
        # With overlap > 0 and the text being longer than one window, the
        # next chunk's start should be before the previous chunk's end.
        assert b.start_char < a.end_char


def test_no_overlap_chunks_dont_regress_start():
    text = "Wort " * 500
    spans = chunk_text(text, chunk_tokens=32, chunk_overlap=0)
    starts = [s.start_char for s in spans]
    assert starts == sorted(starts)


def test_empty_text_yields_no_chunks():
    assert chunk_text("   \n  ", chunk_tokens=32, chunk_overlap=8) == []


def test_page_lookup_is_applied():
    text = "abc" * 100
    calls = []

    def page_lookup(offset: int) -> int:
        calls.append(offset)
        return 1 if offset < 150 else 2

    spans = chunk_text(text, chunk_tokens=16, chunk_overlap=4, page_lookup=page_lookup)
    assert spans
    assert all(s.page in (1, 2) for s in spans)
    assert calls  # page_lookup was actually invoked


def test_invalid_overlap_rejected():
    import pytest

    with pytest.raises(ValueError):
        chunk_text("hello world", chunk_tokens=10, chunk_overlap=10)
