"""Anthropic LLMProvider adapter (default in production).

STUB for Phase 0. Track B (Retrieval+Chat) implements the real Anthropic SDK
calls here — consulting the project's Claude API reference for the exact
streaming + structured-output (`output_config.format`) APIs. Per CLAUDE.md:
the model id is exactly ``claude-haiku-4-5`` (no date suffix); do NOT pass
``thinking``/``effort`` to Haiku 4.5.

The composition root only constructs this adapter when LLM_PROVIDER=anthropic
AND an API key is present; otherwise it falls back to the FakeLLMProvider, so
Phase 0 runs without this being implemented.
"""
from __future__ import annotations

from collections.abc import Iterator

from app.domain.ports.llm import LLMMessage, LLMProvider, LLMResponse

_NOT_IMPLEMENTED = (
    "AnthropicLLMProvider is a Phase-0 stub. Track B implements the real "
    "Anthropic calls. For now run with LLM_PROVIDER=fake (or no API key)."
)


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
        # The SDK client is created lazily by Track B inside complete()/stream()
        # so importing this module never requires the `anthropic` package.

    @property
    def model_id(self) -> str:
        return self._model

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
        raise NotImplementedError(_NOT_IMPLEMENTED)

    def stream(
        self,
        messages: list[LLMMessage],
        *,
        system: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> Iterator[str]:
        raise NotImplementedError(_NOT_IMPLEMENTED)
