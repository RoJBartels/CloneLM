"""Notebook-scoped retrieval: embed query -> vector search -> RetrievedChunks.

This is the first stage of the faithfulness pipeline. It produces the chunks the
grounding prompt is built from and citations are mapped against. It does NOT
talk to the LLM and does NOT decide refusal phrasing — it only reports what the
sources contain (and, optionally, whether the match is too weak to be useful).
"""
from __future__ import annotations

import uuid

from app.domain.models import RetrievedChunk
from app.domain.ports.embeddings import EmbeddingProvider
from app.domain.ports.vector_store import VectorStore


class Retriever:
    """Embeds a query and runs notebook-scoped similarity search.

    ``min_score`` is an optional lightweight threshold: chunks scoring below it
    are dropped so that an off-topic question against a populated notebook can
    still be treated as "weak/empty" retrieval (which drives refusal upstream).
    The vector store always returns cosine *similarity* in ``[~ -1, 1]`` via
    ``RetrievedChunk.score`` (1.0 == identical direction).
    """

    def __init__(
        self,
        vector_store: VectorStore,
        embedder: EmbeddingProvider,
        *,
        min_score: float | None = None,
    ) -> None:
        self._vector_store = vector_store
        self._embedder = embedder
        self._min_score = min_score

    def retrieve(
        self,
        *,
        notebook_id: uuid.UUID,
        query: str,
        top_k: int,
        source_ids: list[uuid.UUID] | None = None,
    ) -> list[RetrievedChunk]:
        """Return up to ``top_k`` notebook-scoped chunks most similar to ``query``.

        ``source_ids`` optionally restricts retrieval to the user's selected
        sources. Results are ordered by descending similarity (the store orders
        by ascending cosine distance). When ``min_score`` is configured, chunks
        below the threshold are filtered out.
        """
        if not query.strip():
            return []

        query_embedding = self._embedder.embed_query(query)
        chunks = self._vector_store.search(
            notebook_id=notebook_id,
            query_embedding=query_embedding,
            top_k=top_k,
            source_ids=source_ids,
        )

        if self._min_score is not None:
            chunks = [c for c in chunks if c.score >= self._min_score]

        return chunks
