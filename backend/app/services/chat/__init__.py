"""Chat / grounded-generation service (Track B, Phase 2 — the CORE).

Publishes the reusable grounded-generation core that Studio (Track E) composes:

    from app.services.chat import GroundedGenerator, GroundedResult

``GroundedGenerator.generate(...)`` runs the full faithfulness loop (retrieve ->
numbered grounding prompt -> LLM structured citations -> citation mapping ->
refusal) and is the single place that logic lives. ``prompts`` exposes the
grounding-prompt builder and the citation JSON schema for tasks that need to
customize the instruction.

Depends ONLY on ``domain/ports`` + ``shared``.
"""
from __future__ import annotations

from . import prompts
from .grounding import (
    DEFAULT_REFUSAL_TEXT,
    GroundedGenerator,
    GroundedResult,
)

__all__ = [
    "GroundedGenerator",
    "GroundedResult",
    "DEFAULT_REFUSAL_TEXT",
    "prompts",
]
