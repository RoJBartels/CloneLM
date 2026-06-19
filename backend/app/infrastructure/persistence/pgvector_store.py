"""pgvector implementation of the VectorStore port.

Cosine-distance KNN over the ``chunk.embedding`` column, ALWAYS scoped to a
single notebook (invariant #4) and optionally to the user's selected sources.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import RetrievedChunk
from app.domain.ports.vector_store import VectorStore
from app.infrastructure.persistence import orm


class PgVectorStore(VectorStore):
    def __init__(self, db: Session) -> None:
        self.db = db

    def search(
        self,
        *,
        notebook_id: uuid.UUID,
        query_embedding: list[float],
        top_k: int,
        source_ids: list[uuid.UUID] | None = None,
    ) -> list[RetrievedChunk]:
        distance = orm.ChunkORM.embedding.cosine_distance(query_embedding)
        stmt = (
            select(orm.ChunkORM, distance.label("distance"))
            .where(orm.ChunkORM.notebook_id == notebook_id)
            .where(orm.ChunkORM.embedding.isnot(None))
            .order_by(distance.asc())
            .limit(top_k)
        )
        if source_ids:
            stmt = stmt.where(orm.ChunkORM.source_id.in_(source_ids))

        results: list[RetrievedChunk] = []
        for chunk, dist in self.db.execute(stmt).all():
            source = self.db.get(orm.SourceORM, chunk.source_id)
            results.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    source_id=chunk.source_id,
                    source_title=source.title if source else "",
                    ordinal=chunk.ordinal,
                    text=chunk.text,
                    score=1.0 - float(dist),  # cosine similarity
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                    page=chunk.page,
                )
            )
        return results
