"""Grounded-generation core (Track B, Phase 2 — PUBLISHED for Track E/Studio).

This is the single reusable implementation of the faithfulness loop:

    retrieve (notebook-scoped) -> numbered grounding prompt -> LLM with structured
    citation output -> map citation markers back to real source chunks/spans ->
    refuse when retrieval is empty/weak.

Both chat (Track B) and Studio (Track E) compose ``GroundedGenerator``. Studio
passes a task-specific ``system_instructions`` and may pass the heavy ``model``
(Sonnet) for synthesis; everything else — isolation, citations, refusal — is
shared and identical.

Dependency rule: this module imports only ``domain`` (models + ports) and the
sibling ``prompts`` module + ``shared``. No infrastructure, no vendor SDK.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field

from app.domain.models import CitationDraft, RetrievedChunk
from app.domain.ports.embeddings import EmbeddingProvider
from app.domain.ports.llm import LLMMessage, LLMProvider
from app.domain.ports.vector_store import VectorStore
from app.services.chat import prompts
from app.services.retrieval import Retriever
from app.shared.errors import ProviderError

# Default user-facing refusal (German UI). Used when retrieval is empty/weak so
# we never call the LLM with no grounding context.
DEFAULT_REFUSAL_TEXT = (
    "Die bereitgestellten Quellen enthalten keine Informationen, um diese Frage "
    "zu beantworten."
)


@dataclass
class GroundedResult:
    """Outcome of one grounded generation.

    Attributes:
        text: The grounded answer (or a refusal message when ``refused``).
        citations: Per-claim citations mapped to real source chunks (empty when
            refused). Ordered by marker.
        refused: True when the sources could not support an answer — either
            retrieval was empty/weak (the LLM was not called) or the LLM itself
            produced an answer with no usable citations.
        retrieved: The chunks retrieval returned (for debugging / Studio reuse).
    """

    text: str
    citations: list[CitationDraft] = field(default_factory=list)
    refused: bool = False
    retrieved: list[RetrievedChunk] = field(default_factory=list)


class GroundedGenerator:
    """Reusable retrieve -> ground -> cite -> (refuse) pipeline.

    Construct once per request with the injected ports, then call ``generate``.
    Studio composes the same instance with a different ``system_instructions``
    and/or ``model``.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        embedder: EmbeddingProvider,
        llm: LLMProvider,
        *,
        default_top_k: int = 8,
        min_score: float | None = None,
        max_tokens: int = 1024,
    ) -> None:
        self._llm = llm
        self._retriever = Retriever(vector_store, embedder, min_score=min_score)
        self._default_top_k = default_top_k
        self._max_tokens = max_tokens

    def generate(
        self,
        *,
        notebook_id: uuid.UUID,
        query: str,
        source_ids: list[uuid.UUID] | None = None,
        top_k: int | None = None,
        system_instructions: str | None = None,
        model: str | None = None,
        refusal_text: str = DEFAULT_REFUSAL_TEXT,
    ) -> GroundedResult:
        """Run the full grounded pipeline for a single notebook-scoped query.

        Args:
            notebook_id: The active notebook. Retrieval is scoped to it; no
                cross-notebook content can leak in (invariant #4).
            query: The user question (chat) or task driver (Studio).
            source_ids: Optional restriction to user-selected sources.
            top_k: Retrieval breadth; defaults to the configured value.
            system_instructions: Task-specific instruction for the grounding
                prompt. Defaults to grounded Q&A. Studio passes its own.
            model: Optional model override (e.g. the heavy model for Studio).
            refusal_text: User-facing refusal message when retrieval is empty.

        Returns:
            A ``GroundedResult``. ``refused`` is True (and ``citations`` empty)
            whenever the sources can't support a grounded, cited answer.
        """
        retrieved = self._retriever.retrieve(
            notebook_id=notebook_id,
            query=query,
            top_k=top_k or self._default_top_k,
            source_ids=source_ids,
        )

        # Empty/weak retrieval -> refuse WITHOUT calling the LLM. This is the
        # architectural guarantee that we never answer from world knowledge.
        if not retrieved:
            return GroundedResult(
                text=refusal_text, citations=[], refused=True, retrieved=[]
            )

        system = prompts.build_system_prompt(
            retrieved, task_instruction=system_instructions
        )
        messages = [LLMMessage(role="user", content=query)]

        try:
            response = self._llm.complete(
                messages,
                system=system,
                model=model,
                max_tokens=self._max_tokens,
                temperature=0.0,
                json_schema=prompts.CITATION_RESPONSE_SCHEMA,
            )
        except ProviderError:
            raise
        except Exception as exc:  # wrap any non-ProviderError from the adapter
            raise ProviderError(f"LLM completion failed: {exc}") from exc

        answer, raw_citations = _parse_structured(response.text)
        citations = self._map_citations(raw_citations, retrieved)

        # An answer with no usable citations cannot be trusted as grounded:
        # treat it as a refusal so the UI never shows uncited claims.
        if not citations:
            return GroundedResult(
                text=answer or refusal_text,
                citations=[],
                refused=True,
                retrieved=retrieved,
            )

        return GroundedResult(
            text=answer,
            citations=citations,
            refused=False,
            retrieved=retrieved,
        )

    def _map_citations(
        self,
        raw_citations: list[dict],
        retrieved: list[RetrievedChunk],
    ) -> list[CitationDraft]:
        """Map LLM citation markers -> the actual RetrievedChunk -> CitationDraft.

        The marker is 1-based and indexes ``retrieved`` positionally (matching
        ``prompts.build_context_block``). Out-of-range or duplicate markers are
        dropped. The snippet prefers the model's verbatim quote (the exact
        supporting passage); we fall back to the chunk text if no quote is given.
        """
        drafts: list[CitationDraft] = []
        seen: set[int] = set()
        for raw in raw_citations:
            marker = raw.get("marker")
            if not isinstance(marker, int):
                continue
            idx = marker - 1
            if idx < 0 or idx >= len(retrieved):
                continue
            if marker in seen:
                continue
            seen.add(marker)

            chunk = retrieved[idx]
            quote = raw.get("quote")
            snippet = quote if isinstance(quote, str) and quote.strip() else chunk.text
            drafts.append(
                CitationDraft(
                    chunk_id=chunk.chunk_id,
                    source_id=chunk.source_id,
                    source_title=chunk.source_title,
                    marker=marker,
                    snippet=snippet,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                    page=chunk.page,
                )
            )

        drafts.sort(key=lambda d: d.marker)
        return drafts


def _parse_structured(text: str) -> tuple[str, list[dict]]:
    """Parse the structured-output JSON into (answer, raw_citations).

    Tolerant of a non-JSON response (e.g. a provider that ignored the schema):
    returns the raw text as the answer with no citations, which the caller will
    treat as a refusal.
    """
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text, []

    if not isinstance(payload, dict):
        return text, []

    answer = payload.get("answer", "")
    if not isinstance(answer, str):
        answer = str(answer)

    citations = payload.get("citations", [])
    if not isinstance(citations, list):
        citations = []
    citations = [c for c in citations if isinstance(c, dict)]

    return answer, citations
