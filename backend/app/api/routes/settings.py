"""Settings router — manage the active model configuration from the UI.

Two modes (see Settings.deployed):
- Localhost: pick Anthropic (Claude) or a local Ollama model and store the
  Anthropic key in backend/.env (the original single-tenant behaviour).
- Deployed: manage the SIGNED-IN USER's own keys (Anthropic + Voyage), stored
  Fernet-encrypted on their account row — never in .env, never echoed back.

Keys are write-only in both modes: GET reports only whether each one is set.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_cipher, get_current_user, get_user_repo, ollama_available, rebind_llm
from app.config import get_settings, update_env_values
from app.domain.models import LLMSettings, LLMSettingsUpdate, User
from app.domain.ports.auth import SecretCipher
from app.domain.ports.repositories import UserRepository

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _current(user: User) -> LLMSettings:
    s = get_settings()
    if s.deployed:
        # Per-user: reflect the signed-in user's stored keys.
        has_anthropic = bool(user.anthropic_key_encrypted)
        return LLMSettings(
            llm_provider="anthropic",
            effective_llm_provider="anthropic" if has_anthropic else "fake",
            llm_model=s.llm_model,
            anthropic_api_key_set=has_anthropic,
            voyage_api_key_set=bool(user.voyage_key_encrypted),
            ollama_base_url=s.ollama_base_url,
            ollama_model=s.ollama_model,
            ollama_available=False,
            deployed=True,
        )
    # Localhost: server-level env config.
    return LLMSettings(
        llm_provider=s.llm_provider,
        effective_llm_provider=s.effective_llm_provider,
        llm_model=s.llm_model,
        anthropic_api_key_set=bool(s.anthropic_api_key),
        voyage_api_key_set=bool(s.voyage_api_key),
        ollama_base_url=s.ollama_base_url,
        ollama_model=s.ollama_model,
        ollama_available=ollama_available(s.ollama_base_url),
        deployed=False,
    )


@router.get("", response_model=LLMSettings)
def get_llm_settings(user: User = Depends(get_current_user)) -> LLMSettings:
    return _current(user)


@router.put("", response_model=LLMSettings)
def update_llm_settings(
    body: LLMSettingsUpdate,
    user: User = Depends(get_current_user),
    user_repo: UserRepository = Depends(get_user_repo),
    cipher: SecretCipher = Depends(get_cipher),
) -> LLMSettings:
    s = get_settings()

    if s.deployed:
        # Encrypt + persist only the keys the user actually supplied (blank =
        # keep existing). Providers are built per request, so this takes effect
        # immediately — no rebind needed.
        enc_anthropic = cipher.encrypt(body.anthropic_api_key) if body.anthropic_api_key else None
        enc_voyage = cipher.encrypt(body.voyage_api_key) if body.voyage_api_key else None
        if enc_anthropic or enc_voyage:
            user = (
                user_repo.update_keys(
                    user.id,
                    anthropic_key_encrypted=enc_anthropic,
                    voyage_key_encrypted=enc_voyage,
                )
                or user
            )
        return _current(user)

    # Localhost: persist to .env + rebind the cached provider (original flow).
    updates: dict[str, str] = {}
    if body.anthropic_api_key:
        updates["anthropic_api_key"] = body.anthropic_api_key
    if body.llm_provider is not None:
        updates["llm_provider"] = body.llm_provider
    if body.ollama_base_url is not None:
        updates["ollama_base_url"] = body.ollama_base_url.strip()
    if body.ollama_model is not None:
        updates["ollama_model"] = body.ollama_model.strip()

    if updates:
        update_env_values(updates)
        rebind_llm()

    return _current(user)
