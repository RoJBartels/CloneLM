"""Retrieval service (Track B, Phase 2).

Embeds a query via the EmbeddingProvider and runs notebook-scoped vector search
through the VectorStore port. Notebook isolation is enforced in the store
(invariant #4) — this layer never widens the scope.

Depends ONLY on ``domain/ports`` + ``shared`` (the inward-pointing dependency
rule). No SQLAlchemy, no vendor SDK.
"""
from __future__ import annotations

from .retriever import Retriever

__all__ = ["Retriever"]
