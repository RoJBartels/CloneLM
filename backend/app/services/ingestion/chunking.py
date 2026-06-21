"""Token-aware sliding-window chunker.

Splits the full extracted text of a source into overlapping chunks sized in
tokens (using ``tiktoken``'s ``cl100k_base`` encoding purely as a sizing ruler
— the actual embedding model is bge-m3). Each chunk preserves the exact
``start_char``/``end_char`` span into the source's full text so the UI can
highlight the precise supporting passage for a citation.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import tiktoken

_ENCODING = tiktoken.get_encoding("cl100k_base")


@dataclass
class ChunkSpan:
    """One chunk's text + position, before embedding/persistence."""

    ordinal: int
    text: str
    start_char: int
    end_char: int
    token_count: int
    page: int | None = None
    metadata: dict = field(default_factory=dict)


def chunk_text(
    text: str,
    *,
    chunk_tokens: int,
    chunk_overlap: int,
    page_lookup=None,
) -> list[ChunkSpan]:
    """Split ``text`` into token-sized chunks with overlap.

    ``page_lookup``, if given, is a callable ``(char_offset) -> int | None``
    used to stamp a page number onto each chunk (PDF sources).
    """
    if not text.strip():
        return []
    if chunk_tokens <= 0:
        raise ValueError("chunk_tokens must be positive")
    if chunk_overlap < 0 or chunk_overlap >= chunk_tokens:
        raise ValueError("chunk_overlap must be >= 0 and < chunk_tokens")

    # Encode once; tiktoken gives us a token list with no native offset
    # mapping, so we re-decode each window's tokens and locate it in `text`
    # via a forward-scanning cursor to recover exact char offsets.
    tokens = _ENCODING.encode(text)
    if not tokens:
        return []

    stride = chunk_tokens - chunk_overlap
    spans: list[ChunkSpan] = []
    search_cursor = 0
    ordinal = 0
    token_start = 0
    n_tokens = len(tokens)

    while token_start < n_tokens:
        token_end = min(token_start + chunk_tokens, n_tokens)
        window = tokens[token_start:token_end]
        chunk_str = _ENCODING.decode(window)

        # Locate this decoded chunk in the original text starting from the
        # last known position (text is consumed monotonically left-to-right).
        start_char = text.find(chunk_str, search_cursor)
        if start_char == -1:
            # Decoding round-trip can introduce whitespace differences
            # (e.g. BPE merges across original whitespace). Fall back to a
            # tolerant search from the very start.
            start_char = text.find(chunk_str)
        if start_char == -1:
            # Last resort: skip this window rather than emit a bad offset.
            token_start += stride
            continue

        end_char = start_char + len(chunk_str)
        page = page_lookup(start_char) if page_lookup else None

        spans.append(
            ChunkSpan(
                ordinal=ordinal,
                text=chunk_str,
                start_char=start_char,
                end_char=end_char,
                token_count=len(window),
                page=page,
            )
        )
        ordinal += 1
        # Advance the search cursor conservatively: allow re-finding overlap
        # text, but never move backwards.
        search_cursor = max(search_cursor, start_char)

        if token_end >= n_tokens:
            break
        token_start += stride

    return spans
