"""Settings router — manage the active LLM provider from the UI.

Lets the user pick Anthropic (Claude) or a local open-source model (Ollama) and
store the Anthropic API key. Changes are persisted to backend/.env (the project's
"secrets via environment only" invariant — never committed) and applied live by
rebinding the cached LLM provider. The API key is write-only: GET never returns
it, only whether one is set.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import ollama_available, rebind_llm
from app.config import get_settings, update_env_values
from app.domain.models import LLMSettings, LLMSettingsUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _current() -> LLMSettings:
    s = get_settings()
    return LLMSettings(
        llm_provider=s.llm_provider,
        effective_llm_provider=s.effective_llm_provider,
        llm_model=s.llm_model,
        anthropic_api_key_set=bool(s.anthropic_api_key),
        ollama_base_url=s.ollama_base_url,
        ollama_model=s.ollama_model,
        ollama_available=ollama_available(s.ollama_base_url),
    )


@router.get("", response_model=LLMSettings)
def get_llm_settings() -> LLMSettings:
    return _current()


@router.put("", response_model=LLMSettings)
def update_llm_settings(body: LLMSettingsUpdate) -> LLMSettings:
    updates: dict[str, str] = {}
    if body.llm_provider is not None:
        updates["llm_provider"] = body.llm_provider
    # Empty string = "keep existing key"; only persist a non-blank secret.
    if body.anthropic_api_key:
        updates["anthropic_api_key"] = body.anthropic_api_key
    if body.ollama_base_url is not None:
        updates["ollama_base_url"] = body.ollama_base_url.strip()
    if body.ollama_model is not None:
        updates["ollama_model"] = body.ollama_model.strip()

    if updates:
        update_env_values(updates)  # writes .env + os.environ, clears settings cache
        rebind_llm()  # next request binds the newly selected provider

    return _current()
