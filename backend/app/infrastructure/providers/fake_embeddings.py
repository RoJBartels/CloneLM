"""Deterministic fake EmbeddingProvider — no ML dependencies.

Produces stable, L2-normalized vectors from a text hash so retrieval is
repeatable in tests and the full UI loop works without the heavy bge-m3 model.
Identical text -> identical vector; similar text is NOT semantically close
(this is a stand-in, not a real model)."""
from __future__ import annotations

import hashlib
import math

from app.domain.ports.embeddings import EmbeddingProvider


class FakeEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dim: int = 1024) -> None:
        self._dim = dim

    @property
    def model_id(self) -> str:
        return "fake-embeddings-v1"

    @property
    def dim(self) -> int:
        return self._dim

    def _vector(self, text: str) -> list[float]:
        # Expand a digest into `dim` floats deterministically, then normalize.
        values: list[float] = []
        counter = 0
        while len(values) < self._dim:
            digest = hashlib.sha256(f"{counter}:{text}".encode()).digest()
            for b in digest:
                values.append((b / 255.0) * 2.0 - 1.0)
                if len(values) >= self._dim:
                    break
            counter += 1
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)
