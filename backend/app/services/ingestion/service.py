"""Ingestion orchestration: parse -> chunk -> embed -> persist.

Depends only on domain ports (``EmbeddingProvider``, ``SourceRepository``,
``ChunkRepository``) plus this module's own parsing/chunking helpers —
never on infrastructure or a vendor SDK directly. The route composes this
service with concrete adapters injected via ``api/deps.py``.
"""
from __future__ import annotations

import uuid

import httpx

from app.domain.models import Chunk, Source, SourceStatus, SourceType
from app.domain.ports.embeddings import EmbeddingProvider
from app.domain.ports.repositories import ChunkRepository, SourceRepository
from app.services.ingestion.chunking import chunk_text
from app.services.ingestion.parsing import extract_html, extract_pdf, extract_plain_text
from app.shared.errors import UnsupportedSourceError, ValidationError
from app.shared.logging import get_logger

log = get_logger(__name__)

_TEXT_EXTENSIONS = (".txt", ".md", ".markdown")
_PDF_EXTENSIONS = (".pdf",)


class IngestionService:
    def __init__(
        self,
        *,
        source_repo: SourceRepository,
        chunk_repo: ChunkRepository,
        embedder: EmbeddingProvider,
        chunk_tokens: int,
        chunk_overlap: int,
        chunk_strategy: str,
    ) -> None:
        self._sources = source_repo
        self._chunks = chunk_repo
        self._embedder = embedder
        self._chunk_tokens = chunk_tokens
        self._chunk_overlap = chunk_overlap
        self._chunk_strategy = chunk_strategy

    def add_source(
        self,
        *,
        notebook_id: uuid.UUID,
        type: SourceType,
        title: str | None,
        content: str | None,
        url: str | None,
        filename: str | None,
        file_bytes: bytes | None,
    ) -> Source:
        """Create the source row, then process it inline. Parse/chunk/embed
        failures are caught and surface as ``status=error`` on the returned
        Source rather than raising — the caller (route) returns 201 either way.
        """
        resolved_title = title or self._default_title(type, filename, url, content)
        uri = url if type == SourceType.url else filename

        source = self._sources.create(
            notebook_id=notebook_id, type=type, title=resolved_title, uri=uri
        )

        try:
            text, page_lookup = self._extract(
                type=type, content=content, url=url, file_bytes=file_bytes, filename=filename
            )
            spans = chunk_text(
                text,
                chunk_tokens=self._chunk_tokens,
                chunk_overlap=self._chunk_overlap,
                page_lookup=page_lookup,
            )
            if not spans:
                raise ValidationError("Extracted text was empty — nothing to ingest.")

            chunks = [
                Chunk(
                    id=uuid.uuid4(),
                    source_id=source.id,
                    notebook_id=notebook_id,
                    ordinal=span.ordinal,
                    text=span.text,
                    token_count=span.token_count,
                    start_char=span.start_char,
                    end_char=span.end_char,
                    page=span.page,
                    metadata={"chunk_strategy": self._chunk_strategy},
                )
                for span in spans
            ]
            embeddings = self._embedder.embed_documents([c.text for c in chunks])
            self._chunks.add_many(
                chunks, embeddings, embedding_model=self._embedder.model_id
            )

            self._sources.set_status(source.id, SourceStatus.ready)
        except (UnsupportedSourceError, ValidationError):
            # Caller-input problems (bad type/missing field/unsupported
            # format) are 4xx-worthy, not a per-source processing failure —
            # let the route map them to an HTTP error rather than silently
            # parking the source in status=error.
            raise
        except Exception as exc:  # noqa: BLE001 - any parse/embed failure -> status=error
            log.warning("Ingestion failed for source %s: %s", source.id, exc)
            self._sources.set_status(source.id, SourceStatus.error, error=str(exc))

        updated = self._sources.get(source.id)
        return updated if updated is not None else source

    # ------------------------------------------------------------------ #
    # Extraction dispatch
    # ------------------------------------------------------------------ #

    def _extract(
        self,
        *,
        type: SourceType,
        content: str | None,
        url: str | None,
        file_bytes: bytes | None,
        filename: str | None,
    ):
        """Returns (text, page_lookup). page_lookup is None unless PDF."""
        if type == SourceType.paste:
            if not content:
                raise ValidationError("`content` is required for type=paste")
            return extract_plain_text(content).text, None

        if type == SourceType.url:
            if not url:
                raise ValidationError("`url` is required for type=url")
            html = self._fetch_url(url)
            return extract_html(html).text, None

        if type == SourceType.file:
            if file_bytes is None:
                raise ValidationError("`file` is required for type=file")
            ext = _extension(filename)
            if ext in _PDF_EXTENSIONS:
                extracted = extract_pdf(file_bytes)
                return extracted.text, extracted.page_at
            if ext in _TEXT_EXTENSIONS or ext == "":
                return extract_plain_text(file_bytes).text, None
            raise UnsupportedSourceError(f"Unsupported file type: {filename!r}")

        raise UnsupportedSourceError(f"Unsupported source type: {type!r}")

    def _fetch_url(self, url: str) -> str:
        try:
            resp = httpx.get(url, timeout=15.0, follow_redirects=True)
            resp.raise_for_status()
            return resp.text
        except httpx.HTTPError as exc:
            raise ValidationError(f"Could not fetch URL {url!r}: {exc}") from exc

    @staticmethod
    def _default_title(
        type: SourceType, filename: str | None, url: str | None, content: str | None
    ) -> str:
        if type == SourceType.file and filename:
            return filename
        if type == SourceType.url and url:
            return url
        if type == SourceType.paste and content:
            snippet = content.strip().splitlines()[0] if content.strip() else "Eingefügter Text"
            return snippet[:80]
        return "Untitled source"


def _extension(filename: str | None) -> str:
    if not filename or "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()
