"""Domain-level error types. Mapped to HTTP responses in the API layer.

Keeping these here (not in ``api/``) lets services raise meaningful errors
without depending on FastAPI, preserving the inward-pointing dependency rule.
"""
from __future__ import annotations


class CloneLMError(Exception):
    """Base class for all application errors."""


class NotFoundError(CloneLMError):
    """A requested entity does not exist."""


class ValidationError(CloneLMError):
    """Input failed a domain rule (distinct from FastAPI request validation)."""


class UnsupportedSourceError(CloneLMError):
    """A source type / format we cannot ingest."""


class ProviderError(CloneLMError):
    """An external provider (LLM, embeddings, TTS) failed."""


class InsufficientContextError(CloneLMError):
    """Retrieval returned nothing usable — the sources cannot support an answer.

    This is the architectural hook for the faithfulness invariant: the chat
    service raises/handles this to *refuse* rather than answer from world
    knowledge.
    """
