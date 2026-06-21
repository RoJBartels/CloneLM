"""Chat SSE endpoint tests (Track B, Phase 2).

End-to-end against real Postgres for persistence + retrieval, with a custom
fake LLM injected via ``app.dependency_overrides`` (never the real Anthropic
API). Verifies the agreed SSE contract (meta / token / citation / done),
citation persistence, and the refusal path.
"""
from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_llm
from app.domain.ports.llm import LLMProvider, LLMResponse, LLMUsage
from app.infrastructure.persistence import orm
from app.infrastructure.persistence.db import get_sessionmaker
from app.infrastructure.providers.fake_embeddings import FakeEmbeddingProvider
from app.main import app

EMBED_DIM = 1024


class CitingFakeLLM(LLMProvider):
    def __init__(self, answer: str, citations: list[dict]) -> None:
        self._answer = answer
        self._citations = citations

    @property
    def model_id(self) -> str:
        return "citing-fake"

    def complete(self, messages, *, system=None, model=None, max_tokens=None,
                 temperature=0.0, json_schema=None) -> LLMResponse:
        payload = {"answer": self._answer, "citations": self._citations}
        return LLMResponse(text=json.dumps(payload),
                           usage=LLMUsage(input_tokens=1, output_tokens=1))

    def stream(self, messages, *, system=None, model=None, max_tokens=None,
               temperature=0.0):
        yield self._answer


@pytest.fixture
def client(db_available):
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.pop(get_llm, None)


def _seed(texts: list[str]) -> tuple[uuid.UUID, list[str]]:
    """Seed a notebook + ready source + embedded chunks. Return (notebook_id, texts)."""
    embedder = FakeEmbeddingProvider(dim=EMBED_DIM)
    s = get_sessionmaker()()
    try:
        nb = orm.NotebookORM(title=f"Chat-{uuid.uuid4().hex[:8]}")
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
        return nb.id, texts
    finally:
        s.close()


def _parse_sse(raw: str) -> list[tuple[str, dict]]:
    """Parse the SSE body into a list of (event, data-dict)."""
    events: list[tuple[str, dict]] = []
    event_name: str | None = None
    for line in raw.splitlines():
        if line.startswith("event:"):
            event_name = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data = line[len("data:"):].strip()
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                payload = {"_raw": data}
            events.append((event_name or "message", payload))
            event_name = None
    return events


def test_grounded_chat_happy_path(client):
    text = "The Eiffel Tower is 330 metres tall."
    nb_id, _ = _seed([text])

    app.dependency_overrides[get_llm] = lambda: CitingFakeLLM(
        answer="Es ist 330 Meter hoch [1].",
        citations=[{"marker": 1, "quote": text}],
    )

    resp = client.post(f"/api/notebooks/{nb_id}/chat",
                       json={"message": text})
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    kinds = [e for e, _ in events]

    assert kinds[0] == "meta"
    assert "conversation_id" in events[0][1]
    assert "user_message_id" in events[0][1]
    assert "token" in kinds
    assert "citation" in kinds
    assert kinds[-1] == "done"

    # Reassemble streamed tokens -> the full answer.
    answer = "".join(d["text"] for e, d in events if e == "token")
    assert answer == "Es ist 330 Meter hoch [1]."

    citation = next(d for e, d in events if e == "citation")
    assert citation["marker"] == 1
    assert citation["snippet"] == text
    assert citation["message_id"] is not None

    done = events[-1][1]
    assert done["refused"] is False
    conv_id = done["conversation_id"]
    msg_id = done["message_id"]

    # Citations were persisted on the assistant message.
    messages = client.get(f"/api/conversations/{conv_id}/messages").json()
    assistant = next(m for m in messages if m["id"] == msg_id)
    assert assistant["role"] == "assistant"
    assert len(assistant["citations"]) == 1
    assert assistant["citations"][0]["marker"] == 1
    # The user turn was persisted too.
    assert any(m["role"] == "user" for m in messages)


def test_refusal_when_no_chunks(client):
    # Notebook with no ready chunks -> empty retrieval -> refusal.
    s = get_sessionmaker()()
    try:
        nb = orm.NotebookORM(title=f"Empty-{uuid.uuid4().hex[:8]}")
        s.add(nb)
        s.commit()
        nb_id = nb.id
    finally:
        s.close()

    # If the LLM were called the test would still pass on refusal, but the
    # generator must not call it; inject one that would error if used.
    class ExplodingLLM(CitingFakeLLM):
        def complete(self, *a, **k):  # noqa: ANN002, ANN003
            raise AssertionError("LLM must not be called on empty retrieval")

    app.dependency_overrides[get_llm] = lambda: ExplodingLLM("", [])

    resp = client.post(f"/api/notebooks/{nb_id}/chat",
                       json={"message": "Anything at all?"})
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    kinds = [e for e, _ in events]

    assert kinds[0] == "meta"
    assert "citation" not in kinds
    done = events[-1]
    assert done[0] == "done"
    assert done[1]["refused"] is True

    # No citations persisted.
    conv_id = done[1]["conversation_id"]
    messages = client.get(f"/api/conversations/{conv_id}/messages").json()
    assistant = next(m for m in messages if m["role"] == "assistant")
    assert assistant["citations"] == []


def test_unknown_notebook_returns_404(client):
    app.dependency_overrides[get_llm] = lambda: CitingFakeLLM("x", [])
    resp = client.post(f"/api/notebooks/{uuid.uuid4()}/chat",
                       json={"message": "hi"})
    assert resp.status_code == 404


def test_conversation_reused_across_turns(client):
    text = "Wasser kocht bei 100 Grad Celsius."
    nb_id, _ = _seed([text])
    app.dependency_overrides[get_llm] = lambda: CitingFakeLLM(
        answer="Bei 100 Grad [1].", citations=[{"marker": 1, "quote": text}]
    )

    r1 = client.post(f"/api/notebooks/{nb_id}/chat", json={"message": text})
    conv_id = _parse_sse(r1.text)[-1][1]["conversation_id"]

    r2 = client.post(
        f"/api/notebooks/{nb_id}/chat",
        json={"message": text, "conversation_id": conv_id},
    )
    assert _parse_sse(r2.text)[-1][1]["conversation_id"] == conv_id

    messages = client.get(f"/api/conversations/{conv_id}/messages").json()
    # Two user + two assistant turns in one conversation.
    assert sum(1 for m in messages if m["role"] == "user") == 2
    assert sum(1 for m in messages if m["role"] == "assistant") == 2
