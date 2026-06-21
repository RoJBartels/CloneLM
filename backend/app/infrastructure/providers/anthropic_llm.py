"""Anthropic LLMProvider adapter (default in production).

The ONLY module allowed to import / call the ``anthropic`` SDK (invariant #5).
Everything else speaks the ``LLMProvider`` port. Per CLAUDE.md: the default
model id is exactly ``claude-haiku-4-5`` (no date suffix); Haiku 4.5 does NOT
accept ``thinking``/``effort`` and is not in the adaptive-thinking family, so we
never pass those. ``temperature`` IS accepted (default 0.0). Studio passes the
heavy model id (Sonnet) via the ``model`` override.

Structured, citation-bearing output uses ``output_config.format`` with a
``json_schema`` (preferred over assistant prefills). Streaming uses
``client.messages.stream(...)``.
"""
from __future__ import annotations

from collections.abc import Iterator

import anthropic

from app.domain.ports.llm import LLMMessage, LLMProvider, LLMResponse, LLMUsage
from app.shared.errors import ProviderError


class AnthropicLLMProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str = "claude-haiku-4-5",
        heavy_model: str = "claude-sonnet-4-6",
        default_max_tokens: int = 1024,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._heavy_model = heavy_model
        self._default_max_tokens = default_max_tokens
        self._client = anthropic.Anthropic(api_key=api_key)

    @property
    def model_id(self) -> str:
        return self._model

    @property
    def heavy_model_id(self) -> str:
        """The heavier synthesis model (Sonnet) Studio may request."""
        return self._heavy_model

    def _wire_messages(self, messages: list[LLMMessage]) -> list[dict]:
        return [{"role": m.role, "content": m.content} for m in messages]

    def complete(
        self,
        messages: list[LLMMessage],
        *,
        system: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.0,
        json_schema: dict | None = None,
    ) -> LLMResponse:
        kwargs: dict = {
            "model": model or self._model,
            "max_tokens": max_tokens or self._default_max_tokens,
            "temperature": temperature,
            "messages": self._wire_messages(messages),
        }
        if system is not None:
            kwargs["system"] = system
        if json_schema is not None:
            kwargs["output_config"] = {
                "format": {"type": "json_schema", "schema": json_schema}
            }

        try:
            message = self._client.messages.create(**kwargs)
        except anthropic.AnthropicError as exc:
            raise ProviderError(f"Anthropic completion failed: {exc}") from exc

        text = _first_text(message)
        usage = _usage(message)
        return LLMResponse(text=text, usage=usage)

    def stream(
        self,
        messages: list[LLMMessage],
        *,
        system: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> Iterator[str]:
        kwargs: dict = {
            "model": model or self._model,
            "max_tokens": max_tokens or self._default_max_tokens,
            "temperature": temperature,
            "messages": self._wire_messages(messages),
        }
        if system is not None:
            kwargs["system"] = system

        try:
            with self._client.messages.stream(**kwargs) as stream:
                yield from stream.text_stream
        except anthropic.AnthropicError as exc:
            raise ProviderError(f"Anthropic streaming failed: {exc}") from exc


def _first_text(message) -> str:
    """Return the text of the first text content block (empty if none)."""
    for block in getattr(message, "content", []) or []:
        if getattr(block, "type", None) == "text":
            return block.text
    return ""


def _usage(message) -> LLMUsage:
    usage = getattr(message, "usage", None)
    if usage is None:
        return LLMUsage()
    return LLMUsage(
        input_tokens=getattr(usage, "input_tokens", 0) or 0,
        output_tokens=getattr(usage, "output_tokens", 0) or 0,
    )
