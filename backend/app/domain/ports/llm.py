"""LLMProvider port + the message/response value objects it speaks.

The Anthropic SDK (and any other vendor) is imported ONLY in the adapter that
implements this interface. Services depend on this module, never on a vendor.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field


@dataclass
class LLMMessage:
    role: str  # "user" | "assistant"
    content: str


@dataclass
class LLMUsage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class LLMResponse:
    text: str
    usage: LLMUsage | None = None
    raw: dict = field(default_factory=dict)


class LLMProvider(ABC):
    @property
    @abstractmethod
    def model_id(self) -> str:
        """The default model this provider completes with."""

    @abstractmethod
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
        """One-shot completion. When ``json_schema`` is provided the adapter must
        request a structured (JSON) response conforming to it — the mechanism the
        chat/studio services use to get answer + per-claim citation ids. ``model``
        overrides the default (e.g. a heavier model for Studio synthesis)."""

    @abstractmethod
    def stream(
        self,
        messages: list[LLMMessage],
        *,
        system: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> Iterator[str]:
        """Yield text deltas for streaming chat (SSE)."""
