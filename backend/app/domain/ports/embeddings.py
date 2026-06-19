"""EmbeddingProvider port. Implemented by infrastructure adapters
(bge-m3 local by default; a SaaS fallback is documented). NEVER import a model
library here."""
from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def model_id(self) -> str:
        """Identifier stamped onto each source/chunk (e.g. ``BAAI/bge-m3``).
        Used to detect when a re-embed is required."""

    @property
    @abstractmethod
    def dim(self) -> int:
        """Vector dimension. Must match the pgvector column size."""

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of passages for storage/retrieval."""

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Embed a single query. Some models prepend an instruction here; the
        adapter owns any such asymmetry."""
