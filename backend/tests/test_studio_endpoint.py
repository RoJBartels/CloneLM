"""Studio endpoint tests (Track E, Phase 4).

End-to-end against real Postgres for persistence + retrieval, with a custom
fake LLM + fake embedder injected via ``app.dependency_overrides`` (never the
real Anthropic API). Covers: each kind generates + persists with >=1 citation
mapped to a real chunk, GET list/one, the refusal path (no chunks), and
notebook isolation.
"""
from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_embedder, get_llm
from app.domain.models import StudioKind
from app.domain.ports.llm import LLMProvider, LLMResponse, LLMUsage
from app.infrastructure.persistence import orm
from app.infrastructure.persistence.db import get_sessionmaker
from app.infrastructure.providers.fake_embeddings import FakeEmbeddingProvider
from app.main import app

EMBED_DIM = 1024


class CitingFakeLLM(LLMProvider):
    """Fake LLM that emits canned structured JSON referencing given markers."""

    def __init__(self, answer: str, citations: list[dict]) -> None:
        self._answer = answer
        self._citations = citations
        self.last_model: str | None = None

    @property
    def model_id(self) -> str:
        return "citing-fake"

    def complete(
        self, messages, *, system=None, model=None, max_tokens=None,
        temperature=0.0, json_schema=None,
    ) -> LLMResponse:
        self.last_model = model
        payload = {"answer": self._answer, "citations": self._citations}
        return LLMResponse(
            text=json.dumps(payload), usage=LLMUsage(input_tokens=10, output_tokens=5)
        )

    def stream(self, messages, *, system=None, model=None, max_tokens=None,
               temperature=0.0):
        yield self._answer


class ExplodingLLM(CitingFakeLLM):
    def complete(self, *a, **k):  # noqa: ANN002, ANN003
        raise AssertionError("LLM must not be called on empty retrieval")


@pytest.fixture
def client(db_available):
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.pop(get_llm, None)
    app.dependency_overrides.pop(get_embedder, None)


def _seed(texts: list[str]) -> uuid.UUID:
    """Seed a notebook + ready source + embedded chunks. Return notebook_id."""
    embedder = FakeEmbeddingProvider(dim=EMBED_DIM)
    s = get_sessionmaker()()
    try:
        nb = orm.NotebookORM(title=f"Studio-{uuid.uuid4().hex[:8]}")
        s.add(nb)
        s.flush()
        src = orm.SourceORM(notebook_id=nb.id, type="paste", title="seed source",
                            status="ready")
        s.add(src)
        s.flush()
        for i, t in enumerate(texts):
            s.add(orm.ChunkORM(
                source_id=src.id, notebook_id=nb.id, ordinal=i, text=t,
                start_char=0, end_char=len(t),
                embedding=embedder.embed_documents([t])[0],
                embedding_model=embedder.model_id,
            ))
        s.commit()
        return nb.id
    finally:
        s.close()


def _empty_notebook() -> uuid.UUID:
    s = get_sessionmaker()()
    try:
        nb = orm.NotebookORM(title=f"Empty-{uuid.uuid4().hex[:8]}")
        s.add(nb)
        s.commit()
        return nb.id
    finally:
        s.close()


@pytest.mark.parametrize("kind", [k.value for k in StudioKind])
def test_generate_each_kind_persists_with_citation(client, kind):
    text = "The Eiffel Tower was completed in 1889 in Paris."
    nb_id = _seed([text])

    app.dependency_overrides[get_embedder] = lambda: FakeEmbeddingProvider(EMBED_DIM)
    fake_llm = CitingFakeLLM(
        answer=f"Some grounded {kind} content [1].",
        citations=[{"marker": 1, "quote": text}],
    )
    app.dependency_overrides[get_llm] = lambda: fake_llm

    resp = client.post(f"/api/notebooks/{nb_id}/studio", json={"kind": kind})
    assert resp.status_code == 201, resp.text
    body = resp.json()

    assert body["kind"] == kind
    assert body["title"]
    assert len(body["citations"]) == 1
    cit = body["citations"][0]
    assert cit["marker"] == 1
    assert cit["snippet"] == text

    # Heavy model was used for synthesis (config-driven, not hardcoded).
    assert fake_llm.last_model == "claude-sonnet-4-6"

    # GET one + GET list both return it.
    out_id = body["id"]
    got = client.get(f"/api/studio/{out_id}")
    assert got.status_code == 200
    assert got.json()["id"] == out_id

    listed = client.get(f"/api/notebooks/{nb_id}/studio").json()
    assert any(o["id"] == out_id for o in listed)


def test_refusal_when_no_chunks(client):
    nb_id = _empty_notebook()
    app.dependency_overrides[get_llm] = lambda: ExplodingLLM("", [])

    resp = client.post(
        f"/api/notebooks/{nb_id}/studio", json={"kind": StudioKind.summary.value}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["citations"] == []
    assert body["content"]  # refusal text persisted, not empty

    listed = client.get(f"/api/notebooks/{nb_id}/studio").json()
    assert len(listed) == 1
    assert listed[0]["citations"] == []


def test_unknown_notebook_returns_404(client):
    app.dependency_overrides[get_llm] = lambda: CitingFakeLLM("x", [])
    resp = client.post(
        f"/api/notebooks/{uuid.uuid4()}/studio", json={"kind": StudioKind.summary.value}
    )
    assert resp.status_code == 404


def test_notebook_isolation(client):
    text = "Notebook A has unique content about volcanoes."
    nb_a = _seed([text])
    nb_b = _seed(["Notebook B has different content about oceans."])

    app.dependency_overrides[get_embedder] = lambda: FakeEmbeddingProvider(EMBED_DIM)
    app.dependency_overrides[get_llm] = lambda: CitingFakeLLM(
        answer="Volcanoes [1].", citations=[{"marker": 1, "quote": text}]
    )

    resp = client.post(f"/api/notebooks/{nb_a}/studio", json={"kind": "summary"})
    assert resp.status_code == 201
    out_id = resp.json()["id"]

    listed_a = client.get(f"/api/notebooks/{nb_a}/studio").json()
    listed_b = client.get(f"/api/notebooks/{nb_b}/studio").json()

    assert any(o["id"] == out_id for o in listed_a)
    assert not any(o["id"] == out_id for o in listed_b)
