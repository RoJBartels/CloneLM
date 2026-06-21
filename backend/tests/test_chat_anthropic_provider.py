"""AnthropicLLMProvider unit tests (Track B, Phase 2).

Light tests that the adapter constructs and builds the right request params,
WITHOUT hitting the network. We monkeypatch the underlying ``anthropic`` client
on an already-constructed provider, so the real SDK is never called.

Per CLAUDE.md: model id is exactly ``claude-haiku-4-5``; no ``thinking`` /
``effort`` is ever sent (Haiku 4.5 rejects them); ``temperature`` is allowed;
structured output goes through ``output_config.format`` with the json_schema.
"""
from __future__ import annotations

import types

import pytest

from app.domain.ports.llm import LLMMessage
from app.infrastructure.providers.anthropic_llm import AnthropicLLMProvider
from app.shared.errors import ProviderError


class _Block:
    def __init__(self, type_: str, text: str = "") -> None:
        self.type = type_
        self.text = text


class _Usage:
    def __init__(self, i: int, o: int) -> None:
        self.input_tokens = i
        self.output_tokens = o


class _Message:
    def __init__(self, content, usage) -> None:
        self.content = content
        self.usage = usage


class _RecordingMessages:
    """Stands in for ``client.messages``; records create() kwargs."""

    def __init__(self) -> None:
        self.create_kwargs: dict | None = None

    def create(self, **kwargs):
        self.create_kwargs = kwargs
        return _Message([_Block("text", "grounded answer")], _Usage(7, 3))


def _provider() -> AnthropicLLMProvider:
    # api_key is unused once we monkeypatch the client; construction must not
    # touch the network (anthropic.Anthropic only stores config at init).
    return AnthropicLLMProvider(api_key="test-key", default_max_tokens=512)


def test_provider_constructs_with_expected_models():
    p = _provider()
    assert p.model_id == "claude-haiku-4-5"
    assert p.heavy_model_id == "claude-sonnet-4-6"


def test_complete_builds_params_and_returns_response(monkeypatch):
    p = _provider()
    rec = _RecordingMessages()
    monkeypatch.setattr(p._client, "messages", rec)

    schema = {"type": "object", "additionalProperties": False,
              "required": ["answer"], "properties": {"answer": {"type": "string"}}}
    resp = p.complete(
        [LLMMessage(role="user", content="Hello")],
        system="SYS",
        max_tokens=256,
        temperature=0.0,
        json_schema=schema,
    )

    assert resp.text == "grounded answer"
    assert resp.usage.input_tokens == 7
    assert resp.usage.output_tokens == 3

    kw = rec.create_kwargs
    assert kw["model"] == "claude-haiku-4-5"
    assert kw["max_tokens"] == 256
    assert kw["temperature"] == 0.0
    assert kw["system"] == "SYS"
    assert kw["messages"] == [{"role": "user", "content": "Hello"}]
    # Structured output via output_config.format (not a prefill).
    assert kw["output_config"] == {"format": {"type": "json_schema", "schema": schema}}
    # Never send thinking/effort to Haiku 4.5.
    assert "thinking" not in kw
    assert "effort" not in kw


def test_complete_model_override(monkeypatch):
    p = _provider()
    rec = _RecordingMessages()
    monkeypatch.setattr(p._client, "messages", rec)

    p.complete([LLMMessage(role="user", content="hi")], model="claude-sonnet-4-6")
    assert rec.create_kwargs["model"] == "claude-sonnet-4-6"
    # No json_schema -> no output_config key.
    assert "output_config" not in rec.create_kwargs


def test_complete_wraps_anthropic_errors(monkeypatch):
    import anthropic

    p = _provider()

    class _Boom:
        def create(self, **kwargs):
            raise anthropic.AnthropicError("boom")

    monkeypatch.setattr(p._client, "messages", _Boom())
    with pytest.raises(ProviderError):
        p.complete([LLMMessage(role="user", content="hi")])


def test_stream_yields_text_deltas(monkeypatch):
    p = _provider()

    class _StreamCtx:
        text_stream = iter(["Hel", "lo ", "world"])

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    captured: dict = {}

    class _Messages:
        def stream(self, **kwargs):
            captured.update(kwargs)
            return _StreamCtx()

    monkeypatch.setattr(p._client, "messages", _Messages())

    out = list(p.stream([LLMMessage(role="user", content="hi")], system="S"))
    assert out == ["Hel", "lo ", "world"]
    assert captured["model"] == "claude-haiku-4-5"
    assert captured["system"] == "S"
    assert "thinking" not in captured


def test_stream_wraps_anthropic_errors(monkeypatch):
    import anthropic

    p = _provider()

    class _Messages:
        def stream(self, **kwargs):
            raise anthropic.AnthropicError("stream boom")

    monkeypatch.setattr(p._client, "messages", _Messages())
    with pytest.raises(ProviderError):
        list(p.stream([LLMMessage(role="user", content="hi")]))


def test_first_text_helper_handles_no_text_block():
    from app.infrastructure.providers.anthropic_llm import _first_text

    msg = types.SimpleNamespace(content=[_Block("tool_use")])
    assert _first_text(msg) == ""
