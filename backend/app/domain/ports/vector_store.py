"""VectorStore port: similarity search over chunk embeddings.

Notebook isolation (invariant #4) is enforced *here* — every query is scoped to
a single ``notebook_id`` and no implementation may return cross-notebook chunks.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from app.domain.models import RetrievedChunk


class VectorStore(ABC):
    @abstractmethod
    def search(
        self,
        *,
        notebook_id: uuid.UUID,
        query_embedding: list[float],
        top_k: int,
        source_ids: list[uuid.UUID] | None = None,
    ) -> list[RetrievedChunk]:
        """Return the ``top_k`` most similar chunks within ``notebook_id``.

        ``source_ids`` optionally restricts the search to the user's selected
        sources (the "Alle auswählen" / per-source checkboxes in the UI). An
        implementation MUST always filter by ``notebook_id``.
        """
