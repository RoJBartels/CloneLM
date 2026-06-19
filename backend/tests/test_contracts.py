"""Phase 0 acceptance: the contracts exist and are wired.

These tests need no database — they assert the ports, adapters, composition
root, and OpenAPI surface are all in place so feature tracks can build."""
from __future__ import annotations

import json

from app.api import deps
from app.domain.ports.embeddings import EmbeddingProvider
from app.domain.ports.llm import LLMMessage, LLMProvider
from app.domain.ports.tts import TTSProvider
from app.infrastructure.providers.fake_embeddings import FakeEmbeddingProvider
from app.infrastructure.providers.fake_llm import FakeLLMProvider
from app.infrastructure.providers.fake_tts import FakeTTSProvider

EXPECTED_PATHS = {
    "/health",
    "/api/notebooks",
    "/api/notebooks/{notebook_id}",
    "/api/notebooks/{notebook_id}/sources",
    "/api/sources/{source_id}",
    "/api/notebooks/{notebook_id}/chat",
    "/api/notebooks/{notebook_id}/conversations",
    "/api/conversations/{conversation_id}/messages",
    "/api/notebooks/{notebook_id}/studio",
    "/api/studio/{output_id}",
    "/api/notebooks/{notebook_id}/notes",
    "/api/notes/{note_id}",
    "/api/notebooks/{notebook_id}/audio",
}


def test_openapi_publishes_full_contract(client):
    spec = client.app.openapi()
    assert EXPECTED_PATHS.issubset(set(spec["paths"].keys()))


def test_fakes_implement_their_ports():
    assert isinstance(FakeLLMProvider(), LLMProvider)
    assert isinstance(FakeEmbeddingProvider(), EmbeddingProvider)
    assert isinstance(FakeTTSProvider(), TTSProvider)


def test_composition_root_binds_fakes_when_no_key():
    # conftest forced LLM_PROVIDER/EMBEDDING_PROVIDER=fake.
    llm = deps.get_llm()
    emb = deps.get_embedder()
    tts = deps.get_tts()
    assert isinstance(llm, LLMProvider)
    assert isinstance(emb, EmbeddingProvider)
    assert isinstance(tts, TTSProvider)
    assert llm.model_id == "fake-llm-v1"


def test_fake_embeddings_are_deterministic_and_correct_dim():
    emb = FakeEmbeddingProvider(dim=1024)
    a = emb.embed_query("hallo welt")
    b = emb.embed_query("hallo welt")
    assert len(a) == 1024
    assert a == b
    assert emb.embed_query("etwas anderes") != a


def test_fake_llm_text_and_structured_output():
    llm = FakeLLMProvider()
    msgs = [LLMMessage(role="user", content="Was steht in den Quellen?")]

    plain = llm.complete(msgs)
    assert "Fake-LLM" in plain.text

    schema = {
        "type": "object",
        "properties": {
            "answer": {"type": "string"},
            "citations": {"type": "array"},
        },
    }
    structured = llm.complete(msgs, json_schema=schema)
    parsed = json.loads(structured.text)
    assert "answer" in parsed and isinstance(parsed["answer"], str)
    assert parsed["citations"] == []


def test_fake_llm_streams_text():
    llm = FakeLLMProvider()
    chunks = list(llm.stream([LLMMessage(role="user", content="hi")]))
    assert "".join(chunks).strip().startswith("[Fake-LLM]")
