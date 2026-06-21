"""Grounded-generation core tests (Track B, Phase 2 — the faithfulness core).

Exercises ``GroundedGenerator`` with in-memory fakes (no DB, no Anthropic):
  - happy path: in-source question -> answer with >=1 citation mapped to a real
    chunk with correct source_id + char span;
  - refusal: empty retrieval -> refused, no citations, LLM never called;
  - refusal: LLM returns no usable citations -> refused;
  - bogus / out-of-range markers are dropped.

A custom in-test fake LLM returns canned structured JSON referencing real chunk
markers — the default FakeLLMProvider returns empty citations, so it can't drive
citation mapping.
"""
from __future__ import annotations

import json
import uuid

from app.domain.models import RetrievedChunk
from app.domain.ports.llm import LLMProvider, LLMResponse, LLMUsage
from app.domain.ports.vector_store import VectorStore
from app.services.chat import GroundedGenerator


class StubVectorStore(VectorStore):
    """Returns canned chunks; records whether it was queried + with what scope."""

    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self._chunks = chunks
        self.last_notebook_id: uuid.UUID | None = None
        self.last_source_ids: list[uuid.UUID] | None = None

    def search(self, *, notebook_id, query_embedding, top_k, source_ids=None):
        self.last_notebook_id = notebook_id
        self.last_source_ids = source_ids
        return list(self._chunks[:top_k])


class StubEmbedder:
    model_id = "stub"
    dim = 8

    def embed_documents(self, texts):
        return [[0.0] * self.dim for _ in texts]

    def embed_query(self, text):
        return [0.0] * self.dim


class CitingFakeLLM(LLMProvider):
    """Fake LLM that emits canned structured JSON referencing given markers."""

    def __init__(self, answer: str, citations: list[dict]) -> None:
        self._answer = answer
        self._citations = citations
        self.called = False
        self.last_system: str | None = None
        self.last_model: str | None = None
        self.last_json_schema: dict | None = None

    @property
    def model_id(self) -> str:
        return "citing-fake"

    def complete(
        self, messages, *, system=None, model=None, max_tokens=None,
        temperature=0.0, json_schema=None,
    ) -> LLMResponse:
        self.called = True
        self.last_system = system
        self.last_model = model
        self.last_json_schema = json_schema
        payload = {"answer": self._answer, "citations": self._citations}
        return LLMResponse(
            text=json.dumps(payload), usage=LLMUsage(input_tokens=10, output_tokens=5)
        )

    def stream(self, messages, *, system=None, model=None, max_tokens=None,
               temperature=0.0):
        yield self._answer


def _chunk(text: str, *, ordinal: int, start: int, end: int, title: str,
           source_id: uuid.UUID | None = None) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        source_id=source_id or uuid.uuid4(),
        source_title=title,
        ordinal=ordinal,
        text=text,
        score=0.9,
        start_char=start,
        end_char=end,
        page=ordinal + 1,
    )


def test_happy_path_maps_citation_to_real_chunk():
    src_id = uuid.uuid4()
    chunks = [
        _chunk("Mitochondria are the powerhouse of the cell.", ordinal=0,
               start=10, end=54, title="Biology 101", source_id=src_id),
        _chunk("Chloroplasts perform photosynthesis.", ordinal=1,
               start=80, end=116, title="Biology 101", source_id=src_id),
    ]
    llm = CitingFakeLLM(
        answer="Mitochondria produce the cell's energy [1].",
        citations=[{"marker": 1, "quote": "Mitochondria are the powerhouse of the cell."}],
    )
    gen = GroundedGenerator(StubVectorStore(chunks), StubEmbedder(), llm)

    result = gen.generate(notebook_id=uuid.uuid4(), query="What do mitochondria do?")

    assert result.refused is False
    assert llm.called is True
    assert len(result.citations) == 1
    cit = result.citations[0]
    assert cit.marker == 1
    assert cit.chunk_id == chunks[0].chunk_id
    assert cit.source_id == src_id
    assert cit.start_char == 10 and cit.end_char == 54
    assert cit.page == 1
    assert cit.snippet == "Mitochondria are the powerhouse of the cell."
    # The structured schema was passed to the LLM (structured output).
    assert llm.last_json_schema is not None
    assert "citations" in llm.last_json_schema["properties"]


def test_refusal_when_retrieval_empty_does_not_call_llm():
    llm = CitingFakeLLM(answer="should not be used", citations=[{"marker": 1, "quote": "x"}])
    gen = GroundedGenerator(StubVectorStore([]), StubEmbedder(), llm)

    result = gen.generate(notebook_id=uuid.uuid4(), query="anything")

    assert result.refused is True
    assert result.citations == []
    assert result.retrieved == []
    assert llm.called is False, "must not call the LLM when there is no context"


def test_refusal_when_llm_returns_no_citations():
    chunks = [_chunk("Some content.", ordinal=0, start=0, end=13, title="Doc")]
    llm = CitingFakeLLM(
        answer="Die Quellen decken diese Frage nicht ab.", citations=[]
    )
    gen = GroundedGenerator(StubVectorStore(chunks), StubEmbedder(), llm)

    result = gen.generate(notebook_id=uuid.uuid4(), query="off-topic?")

    assert result.refused is True
    assert result.citations == []
    assert llm.called is True


def test_out_of_range_and_duplicate_markers_are_dropped():
    chunks = [_chunk("Only chunk.", ordinal=0, start=0, end=11, title="Doc")]
    llm = CitingFakeLLM(
        answer="Claim [1][1][2].",
        citations=[
            {"marker": 1, "quote": "Only chunk."},
            {"marker": 1, "quote": "dup"},   # duplicate -> dropped
            {"marker": 2, "quote": "nope"},  # out of range -> dropped
            {"marker": 99, "quote": "nope"},
        ],
    )
    gen = GroundedGenerator(StubVectorStore(chunks), StubEmbedder(), llm)

    result = gen.generate(notebook_id=uuid.uuid4(), query="q")

    assert result.refused is False
    assert [c.marker for c in result.citations] == [1]


def test_source_ids_and_model_passthrough():
    chunks = [_chunk("Content for studio.", ordinal=0, start=0, end=19, title="Doc")]
    store = StubVectorStore(chunks)
    llm = CitingFakeLLM(answer="Summary [1].",
                        citations=[{"marker": 1, "quote": "Content for studio."}])
    gen = GroundedGenerator(store, StubEmbedder(), llm)

    nb_id = uuid.uuid4()
    src_ids = [uuid.uuid4()]
    result = gen.generate(
        notebook_id=nb_id,
        query="summarize",
        source_ids=src_ids,
        system_instructions="Write a faithful summary.",
        model="claude-sonnet-4-6",
    )

    assert result.refused is False
    assert store.last_notebook_id == nb_id
    assert store.last_source_ids == src_ids
    assert llm.last_model == "claude-sonnet-4-6"  # heavy model passthrough (Studio)
    assert "Write a faithful summary." in (llm.last_system or "")


def test_snippet_falls_back_to_chunk_text_when_quote_missing():
    chunks = [_chunk("Full chunk body.", ordinal=0, start=5, end=21, title="Doc")]
    llm = CitingFakeLLM(answer="Claim [1].", citations=[{"marker": 1}])
    gen = GroundedGenerator(StubVectorStore(chunks), StubEmbedder(), llm)

    result = gen.generate(notebook_id=uuid.uuid4(), query="q")

    assert result.citations[0].snippet == "Full chunk body."
