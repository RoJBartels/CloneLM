"""Studio service (Track E, Phase 4).

Generates one-click grounded, cited artifacts (summary / faq / study_guide /
briefing / timeline) by composing Track B's reusable ``GroundedGenerator`` core
with per-kind retrieval queries + task instructions (see ``kinds.py``), then
persists the result via ``StudioOutputRepository``.

No retrieval/citation/refusal logic is reimplemented here — this module only
adds the per-kind framing and persistence.
"""
from __future__ import annotations

import uuid

from app.domain.models import StudioKind, StudioOutput
from app.domain.ports.repositories import StudioOutputRepository
from app.services.chat import GroundedGenerator
from app.services.studio.kinds import get_spec

# Studio summarizes the *whole* notebook, so retrieval must be broader than a
# single chat question. We pass a generous top_k floor regardless of the
# configured chat default.
MIN_STUDIO_TOP_K = 24


class StudioService:
    """Composes the grounded core for one Studio artifact and persists it."""

    def __init__(
        self,
        generator: GroundedGenerator,
        repo: StudioOutputRepository,
        *,
        heavy_model: str,
        top_k: int = MIN_STUDIO_TOP_K,
    ) -> None:
        self._generator = generator
        self._repo = repo
        self._heavy_model = heavy_model
        self._top_k = top_k

    def generate(self, *, notebook_id: uuid.UUID, kind: StudioKind) -> StudioOutput:
        spec = get_spec(kind)

        result = self._generator.generate(
            notebook_id=notebook_id,
            query=spec.query,
            source_ids=None,
            top_k=self._top_k,
            system_instructions=spec.system_instructions,
            model=self._heavy_model,
            refusal_text=spec.refusal_text,
        )

        return self._repo.create(
            notebook_id=notebook_id,
            kind=kind,
            title=spec.title,
            content=result.text,
            citations=result.citations,
        )
