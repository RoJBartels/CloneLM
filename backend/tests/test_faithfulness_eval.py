"""Faithfulness eval set (Phase 7) — the north-star regression gate.

This is a small, **deterministic, offline** eval that proves the architectural
faithfulness guarantees on every CI run (no API key, no ML model):

  - a question the sources SUPPORT -> a grounded answer with >=1 citation mapped
    to a real source chunk (must answer + cite);
  - a question the sources DO NOT support -> a refusal, no citations, and the LLM
    is never asked to answer from world knowledge (must refuse);
  - an answer the model returns WITHOUT usable citations -> treated as a refusal
    (the UI never shows an uncited claim);
  - cross-notebook isolation: a notebook's chunks never leak into another's
    answer.

The *semantic* in-source/out-of-source distinction (e.g. "photosynthesis" asked
of a notebook that only contains a LaTeX manual) needs the real embedding model +
LLM; that is covered by ``scripts/faithfulness_demo.py`` (run locally with real
providers). Here we use controlled fakes so the property holds regardless of
which model is plugged in — faithfulness is architectural, not model-dependent.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field

from app.domain.models import RetrievedChunk
from app.domain.ports.llm import LLMProvider, LLMResponse, LLMUsage
from app.domain.ports.vector_store import VectorStore
from app.services.chat import GroundedGenerator


# --------------------------------------------------------------------------- #
# Test doubles (controlled retrieval + LLM so the eval is deterministic)
# --------------------------------------------------------------------------- #


class ScopedVectorStore(VectorStore):
    """Maps notebook_id -> its chunks, so isolation is testable: a query for one
    notebook can only ever see that notebook's chunks."""

    def __init__(self, by_notebook: dict[uuid.UUID, list[RetrievedChunk]]) -> None:
        self._by_notebook = by_notebook

    def search(self, *, notebook_id, query_embedding, top_k, source_ids=None):
        return list(self._by_notebook.get(notebook_id, [])[:top_k])


class _StubEmbedder:
    model_id = "stub"
    dim = 8

    def embed_documents(self, texts):
        return [[0.0] * self.dim for _ in texts]

    def embed_query(self, text):
        return [0.0] * self.dim


class _ScriptedLLM(LLMProvider):
    """Returns a canned structured answer; records whether it was called (so we
    can assert the LLM is NEVER asked to answer when retrieval is empty)."""

    def __init__(self, answer: str, citations: list[dict]) -> None:
        self._answer = answer
        self._citations = citations
        self.called = False

    @property
    def model_id(self) -> str:
        return "scripted"

    def complete(self, messages, *, system=None, model=None, max_tokens=None,
                 temperature=0.0, json_schema=None) -> LLMResponse:
        self.called = True
        return LLMResponse(
            text=json.dumps({"answer": self._answer, "citations": self._citations}),
            usage=LLMUsage(),
        )

    def stream(self, messages, *, system=None, model=None, max_tokens=None,
               temperature=0.0):
        yield self._answer


def _chunk(text: str, title: str, source_id: uuid.UUID) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid4(), source_id=source_id, source_title=title,
        ordinal=0, text=text, score=0.9, start_char=0, end_char=len(text), page=1,
    )


# --------------------------------------------------------------------------- #
# The eval set
# --------------------------------------------------------------------------- #


@dataclass
class EvalCase:
    name: str
    query: str
    chunks: list[RetrievedChunk]          # what retrieval returns for the notebook
    llm_answer: str                        # what the (fake) model would answer
    llm_citations: list[dict] = field(default_factory=list)
    expect_refused: bool = False
    expect_min_citations: int = 0


_SRC = uuid.uuid4()
_SUPPORTING = [_chunk("The fox is a small, omnivorous mammal.", "Animals", _SRC)]

EVAL_SET: list[EvalCase] = [
    EvalCase(
        name="in_source__answers_and_cites",
        query="What is a fox?",
        chunks=_SUPPORTING,
        llm_answer="A fox is a small omnivorous mammal [1].",
        llm_citations=[{"marker": 1, "quote": "The fox is a small, omnivorous mammal."}],
        expect_refused=False,
        expect_min_citations=1,
    ),
    EvalCase(
        name="out_of_source__refuses_without_calling_llm",
        query="What is the capital of France?",
        chunks=[],  # retrieval finds nothing -> must refuse, LLM untouched
        llm_answer="Paris.",  # would be wrong to use — proves we don't
        llm_citations=[{"marker": 1, "quote": "x"}],
        expect_refused=True,
        expect_min_citations=0,
    ),
    EvalCase(
        name="uncited_answer__treated_as_refusal",
        query="Tell me something.",
        chunks=_SUPPORTING,
        llm_answer="Here is an unsupported claim with no citation.",
        llm_citations=[],  # no citations -> refuse rather than show uncited claim
        expect_refused=True,
        expect_min_citations=0,
    ),
]


def test_faithfulness_eval_set_passes():
    """Every case in the eval set must meet its expected faithfulness behaviour."""
    results = []
    for case in EVAL_SET:
        nb_id = uuid.uuid4()
        store = ScopedVectorStore({nb_id: case.chunks})
        llm = _ScriptedLLM(case.llm_answer, case.llm_citations)
        gen = GroundedGenerator(store, _StubEmbedder(), llm)

        result = gen.generate(notebook_id=nb_id, query=case.query)

        ok = (
            result.refused == case.expect_refused
            and len(result.citations) >= case.expect_min_citations
        )
        # When retrieval is empty the LLM must never be consulted.
        if not case.chunks:
            ok = ok and (llm.called is False)
        results.append((case.name, ok))

    failed = [name for name, ok in results if not ok]
    assert not failed, f"faithfulness eval failures: {failed}"


def test_notebook_isolation_is_a_faithfulness_property():
    """A question answerable from notebook A's sources must REFUSE in notebook B,
    because retrieval is scoped per notebook — no cross-notebook leakage."""
    nb_a, nb_b = uuid.uuid4(), uuid.uuid4()
    store = ScopedVectorStore({nb_a: _SUPPORTING, nb_b: []})
    llm = _ScriptedLLM(
        "A fox is a small mammal [1].",
        [{"marker": 1, "quote": "The fox is a small, omnivorous mammal."}],
    )
    gen = GroundedGenerator(store, _StubEmbedder(), llm)

    in_a = gen.generate(notebook_id=nb_a, query="What is a fox?")
    in_b = gen.generate(notebook_id=nb_b, query="What is a fox?")

    assert in_a.refused is False and len(in_a.citations) == 1
    assert in_b.refused is True and in_b.citations == []
