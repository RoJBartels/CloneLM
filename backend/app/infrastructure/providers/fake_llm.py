"""Deterministic fake LLMProvider — no API key required.

Lets the entire chat/studio loop run locally without Anthropic. It does not
truly reason; it echoes a grounded-style answer derived from the supplied
context so the citation/refusal plumbing can be exercised end to end.

When a ``json_schema`` is supplied it returns a JSON object whose keys are the
schema's properties (filled with type-appropriate defaults), placing the
generated answer in the first string-typed property. This makes it a usable
stand-in for ANY track's structured-output call without that track having to
ship its own fake.
"""
from __future__ import annotations

import json
from collections.abc import Iterator

from app.domain.ports.llm import LLMMessage, LLMProvider, LLMResponse, LLMUsage


class FakeLLMProvider(LLMProvider):
    def __init__(self, model_id: str = "fake-llm-v1") -> None:
        self._model_id = model_id

    @property
    def model_id(self) -> str:
        return self._model_id

    def _answer(self, messages: list[LLMMessage], system: str | None) -> str:
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"), ""
        )
        context_hint = ""
        if system and "QUELLE" in system.upper():
            context_hint = " (Antwort basiert ausschließlich auf den bereitgestellten Quellen.)"
        return (
            f"[Fake-LLM] Basierend auf den Quellen zu deiner Frage "
            f"„{last_user[:160]}“: Dies ist eine deterministische Demo-Antwort "
            f"ohne echtes Modell.{context_hint}"
        )

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
        answer = self._answer(messages, system)
        if json_schema is not None:
            payload = _fill_schema(json_schema, answer)
            text = json.dumps(payload, ensure_ascii=False)
        else:
            text = answer
        return LLMResponse(text=text, usage=LLMUsage(input_tokens=0, output_tokens=0))

    def stream(
        self,
        messages: list[LLMMessage],
        *,
        system: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> Iterator[str]:
        answer = self._answer(messages, system)
        for word in answer.split(" "):
            yield word + " "


def _fill_schema(schema: dict, answer: str):
    """Best-effort: build a value matching a (subset of) JSON Schema."""
    t = schema.get("type")
    if t == "object":
        props: dict = schema.get("properties", {})
        out: dict = {}
        first_string_filled = False
        for key, sub in props.items():
            if sub.get("type") == "string" and not first_string_filled:
                out[key] = answer
                first_string_filled = True
            else:
                out[key] = _fill_schema(sub, answer)
        return out
    if t == "array":
        return []
    if t == "string":
        return answer
    if t in ("number", "integer"):
        return 0
    if t == "boolean":
        return False
    return None
