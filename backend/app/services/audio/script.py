"""Grounded two-host script builder (Track F, Phase 6 — STRETCH).

Reuses the published ``GroundedGenerator`` (Track B core) so the Audio Overview
gets the exact same faithfulness guarantees as chat/Studio: retrieval is
notebook-scoped, generation is conditioned only on retrieved chunks, and the
generator refuses (rather than guessing) when the sources don't support an
overview.

The dialogue itself is carried in the structured ``answer`` string the
``GroundedGenerator`` already produces (it never returns labelled per-speaker
turns — that's not part of the shared citation schema). We instruct the model,
via ``system_instructions``, to write that single string as alternating
``Host A:`` / ``Host B:`` lines, then parse those lines into ``TTSSegment``s
here. If the model ignores the format (or the LLM is a minimal fake in tests),
parsing falls back to a single segment so the pipeline never breaks.
"""
from __future__ import annotations

import re
import uuid

from app.config import get_settings
from app.domain.ports.embeddings import EmbeddingProvider
from app.domain.ports.llm import LLMProvider
from app.domain.ports.tts import TTSSegment
from app.domain.ports.vector_store import VectorStore
from app.services.chat import GroundedGenerator, GroundedResult

# Broad, German query: there is no user question for an Audio Overview, so we
# ask a general "key findings" question that pulls a wide, representative
# sample of the notebook's chunks (top_k is also widened by the caller).
DEFAULT_QUERY = (
    "Die wichtigsten Erkenntnisse und Kernaussagen der Quellen für eine "
    "Hörübersicht."
)

SYSTEM_INSTRUCTIONS = (
    "Write a lively but STRICTLY FAITHFUL two-host podcast dialogue in German "
    "that explains ONLY what the sources say. The two hosts are named exactly "
    '"Host A" and "Host B". Put the ENTIRE dialogue in the "answer" field as '
    "plain text, with each line formatted exactly as `Host A: <text>` or "
    "`Host B: <text>` (one turn per line, alternating speakers naturally). "
    "Hosts may summarize, react to, and build on each other's points, but every "
    "factual claim must still carry an inline citation marker like [1] and be "
    "backed by a verbatim quote, exactly as instructed above. If the sources do "
    "not contain enough information for a meaningful overview, do not invent "
    "content — instead make the ENTIRE dialogue a short, honest admission (in "
    "German, still as Host A / Host B lines) that the sources are insufficient, "
    "and return an empty citations list."
)

_LINE_RE = re.compile(r"^\s*(Host\s*[AB])\s*:\s*(.+)$", re.IGNORECASE)

_SPEAKER_MAP = {"hosta": "host_a", "hostb": "host_b"}


def parse_segments(text: str) -> list[TTSSegment]:
    """Parse a `Host A: ...` / `Host B: ...` line-based script into segments.

    Falls back to a single ``host_a`` segment containing the whole text if no
    recognizable speaker-prefixed line is found, so an LLM that ignores the
    requested format still produces playable audio instead of failing.
    """
    segments: list[TTSSegment] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = _LINE_RE.match(line)
        if not match:
            continue
        key = re.sub(r"\s+", "", match.group(1)).lower()
        speaker = _SPEAKER_MAP.get(key, "host_a")
        content = match.group(2).strip()
        if content:
            segments.append(TTSSegment(speaker=speaker, text=content))

    if segments:
        return segments

    cleaned = text.strip()
    if not cleaned:
        return []
    return [TTSSegment(speaker="host_a", text=cleaned)]


def build_script(
    *,
    notebook_id: uuid.UUID,
    vector_store: VectorStore,
    embedder: EmbeddingProvider,
    llm: LLMProvider,
) -> tuple[list[TTSSegment], GroundedResult]:
    """Run the grounded pipeline and parse its output into TTS segments.

    Returns the parsed segments alongside the raw ``GroundedResult`` so the
    caller can decide how to handle a refusal (see ``AudioService``).
    """
    settings = get_settings()
    generator = GroundedGenerator(vector_store, embedder, llm, max_tokens=2048)

    result = generator.generate(
        notebook_id=notebook_id,
        query=DEFAULT_QUERY,
        top_k=max(settings.retrieval_top_k, 24),
        system_instructions=SYSTEM_INSTRUCTIONS,
        model=settings.llm_model_heavy,
    )

    return parse_segments(result.text), result
