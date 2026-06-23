"""Application settings + provider selection.

This module is half of the composition root (the other half is ``api/deps.py``).
Everything that varies by environment — which LLM/embedding/TTS adapter to bind,
model ids, the database URL, retrieval/chunking tuning — is read here from the
environment. Business logic NEVER reads env directly; it receives a ``Settings``.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# The .env lives at the backend package root (backend/.env), next to pyproject.
# Resolved absolutely so writes work regardless of the process CWD.
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- App ---
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    cors_origins: str = "http://localhost:5173"

    # --- Database ---
    database_url: str = "postgresql+psycopg://clonelm:clonelm@localhost:5432/clonelm"

    # --- LLM provider selection ---
    llm_provider: str = "anthropic"  # anthropic | ollama | fake
    anthropic_api_key: str = ""
    llm_model: str = "claude-haiku-4-5"
    llm_model_heavy: str = "claude-sonnet-4-6"
    llm_max_tokens: int = 1024

    # Open-source local LLM via Ollama (http://localhost:11434). Used when
    # llm_provider == "ollama". heavy model is optional (blank -> use ollama_model).
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    ollama_model_heavy: str = ""
    # Studio artifacts (study guide, briefing, …) are long-form; a chat-sized
    # budget truncates them mid-JSON, dropping content + citations. Give Studio
    # synthesis its own, larger budget.
    studio_max_tokens: int = 4096

    # --- Embeddings provider selection ---
    embedding_provider: str = "bge_m3_local"  # bge_m3_local | fake
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024

    # --- TTS provider selection ---
    tts_provider: str = "piper"  # piper | fake
    # Local Piper neural voices for the two-host Audio Overview. Models are
    # auto-downloaded into piper_voice_dir on first use (or via
    # scripts/download_piper_voices.py). voice_dir is anchored to backend/ when
    # relative. host_a/host_b are deliberately different voices/genders.
    piper_voice_dir: str = "models/piper"
    piper_voice_host_a: str = "de_DE-thorsten-medium"
    piper_voice_host_b: str = "de_DE-kerstin-low"
    piper_sample_rate: int = 22050

    # --- Retrieval / chunking ---
    retrieval_top_k: int = 8
    chunk_tokens: int = 512
    chunk_overlap: int = 64
    chunk_strategy: str = "token_sliding_v1"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def effective_llm_provider(self) -> str:
        """Fall back to the fake LLM when Anthropic is selected but no key is set,
        so the app boots and the full UI loop works in development."""
        if self.llm_provider == "anthropic" and not self.anthropic_api_key:
            return "fake"
        return self.llm_provider

    @property
    def effective_heavy_model(self) -> str:
        """The heavy (Studio/Audio synthesis) model id for the active provider.
        Anthropic uses a distinct Sonnet model; Ollama typically has one model,
        so it reuses ollama_model unless a dedicated heavy model is configured."""
        if self.effective_llm_provider == "ollama":
            return self.ollama_model_heavy or self.ollama_model
        return self.llm_model_heavy


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Env keys that the Settings UI may persist. Mapped from the Settings field name
# (lower) to its UPPER_SNAKE env var name (pydantic is case-insensitive).
_PERSISTABLE_ENV_KEYS = {
    "llm_provider": "LLM_PROVIDER",
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "ollama_base_url": "OLLAMA_BASE_URL",
    "ollama_model": "OLLAMA_MODEL",
    "ollama_model_heavy": "OLLAMA_MODEL_HEAVY",
}


def update_env_values(values: dict[str, str]) -> None:
    """Persist settings to backend/.env (gitignored) AND the live process env,
    then drop the cached Settings so the next read reflects the change.

    Writing to os.environ too is required because pydantic-settings ranks real
    environment variables ABOVE the .env file — without it a value already
    exported in the shell would shadow the freshly written .env entry.
    """
    env_names = {_PERSISTABLE_ENV_KEYS[k]: v for k, v in values.items() if k in _PERSISTABLE_ENV_KEYS}
    if not env_names:
        return

    lines: list[str] = []
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()

    seen: set[str] = set()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name = stripped.split("=", 1)[0].strip()
        if name in env_names:
            lines[i] = f"{name}={env_names[name]}"
            seen.add(name)
    for name, value in env_names.items():
        if name not in seen:
            lines.append(f"{name}={value}")

    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    for name, value in env_names.items():
        os.environ[name] = value

    get_settings.cache_clear()
