"""Ollama LLMProvider adapter — local, open-source models.

The ONLY module allowed to talk to an Ollama server (invariant #5). Everything
else speaks the ``LLMProvider`` port. Ollama runs open-weight models (Llama,
Qwen, Mistral, …) locally and exposes an HTTP API on ``OLLAMA_BASE_URL``
(default ``http://localhost:11434``); no API key and no network egress.

Structured, citation-bearing output uses Ollama's ``format`` field (a JSON
schema, supported since Ollama 0.5) — the same mechanism the Anthropic adapter
gets from ``output_config.format``. Streaming consumes the newline-delimited
JSON stream from ``/api/chat``.
"""
from __future__ import annotations

import json
from collections.abc import Iterator

import httpx

from app.domain.ports.llm import LLMMessage, LLMProvider, LLMResponse, LLMUsage
from app.shared.errors import ProviderError

# Local generation can be slow on CPU; be generous so we don't abort mid-answer.
_TIMEOUT_S = 600.0


class OllamaLLMProvider(LLMProvider):
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.1",
        heavy_model: str = "",
        default_max_tokens: int = 1024,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._heavy_model = heavy_model or model
        self._default_max_tokens = default_max_tokens

    @property
    def model_id(self) -> str:
        return self._model

    @property
    def heavy_model_id(self) -> str:
        return self._heavy_model

    def _wire_messages(
        self, messages: list[LLMMessage], system: str | None
    ) -> list[dict]:
        wire: list[dict] = []
        if system is not None:
            wire.append({"role": "system", "content": system})
        wire.extend({"role": m.role, "content": m.content} for m in messages)
        return wire

    def _body(
        self,
        messages: list[LLMMessage],
        *,
        system: str | None,
        model: str | None,
        max_tokens: int | None,
        temperature: float,
        stream: bool,
        json_schema: dict | None = None,
    ) -> dict:
        body: dict = {
            "model": model or self._model,
            "messages": self._wire_messages(messages, system),
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens or self._default_max_tokens,
            },
        }
        if json_schema is not None:
            body["format"] = json_schema
        return body

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
        body = self._body(
            messages,
            system=system,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=False,
            json_schema=json_schema,
        )
        try:
            resp = httpx.post(
                f"{self._base_url}/api/chat", json=body, timeout=_TIMEOUT_S
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Ollama completion failed: {exc}") from exc

        text = (data.get("message") or {}).get("content", "") or ""
        usage = LLMUsage(
            input_tokens=data.get("prompt_eval_count", 0) or 0,
            output_tokens=data.get("eval_count", 0) or 0,
        )
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
        body = self._body(
            messages,
            system=system,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        )
        try:
            with httpx.stream(
                "POST", f"{self._base_url}/api/chat", json=body, timeout=_TIMEOUT_S
            ) as resp:
                resp.raise_for_status()
                # Ollama emits one JSON object per line; each carries an
                # incremental message delta until the final {"done": true}.
                for line in resp.iter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    piece = (chunk.get("message") or {}).get("content", "")
                    if piece:
                        yield piece
                    if chunk.get("done"):
                        break
        except httpx.HTTPError as exc:
            raise ProviderError(f"Ollama streaming failed: {exc}") from exc

    def is_available(self) -> bool:
        """Best-effort liveness probe for the local Ollama server."""
        try:
            resp = httpx.get(f"{self._base_url}/api/tags", timeout=2.0)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False
