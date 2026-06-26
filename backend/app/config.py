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

from pydantic import field_validator, model_validator
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

    # Deployment mode. The single switch between the local and hosted builds:
    #   False (localhost): bge-m3 embeddings run locally; the user may also pick
    #          a local open-source LLM (Ollama) from the Settings UI.
    #   True  (deployed, e.g. Railway): embeddings come from Voyage AI (a hosted
    #          API, no GPU needed); the LLM is Anthropic only — the local-model
    #          option is hidden so there is nothing local to run.
    # The embedding model is NOT user-selectable: it is derived from this flag so
    # a notebook's vectors can never be mixed across embedding models.
    deployed: bool = False

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
    # Not user-selectable — chosen from `deployed` (see effective_embedding_provider)
    # so the vector space stays consistent within a notebook. bge-m3 (local) and
    # voyage-3.5 (hosted) both emit 1024-dim vectors, so the pgvector column size
    # (embedding_dim) — and therefore the schema — is identical in both modes.
    embedding_provider: str = "bge_m3_local"  # bge_m3_local | fake
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024

    # Hosted embeddings via Voyage AI (an Anthropic company), used when deployed.
    # In the multi-user deployed build the key is per-user (not read from here);
    # this server-level value is only the localhost/single-tenant fallback.
    # voyage-3.5 defaults to 1024-dim output, matching embedding_dim above.
    voyage_api_key: str = ""
    voyage_model: str = "voyage-3.5"

    # --- Auth (deployed build only; see DEPLOYED) ---
    # JWT signing secret and the Fernet master key that encrypts users' API keys
    # at rest. REQUIRED when deployed (validated below) — generate strong random
    # values and set them as env vars; never commit. A Fernet key is a urlsafe
    # base64-encoded 32-byte value (see SECRET_ENCRYPTION_KEY in .env.example).
    jwt_secret: str = ""
    secret_encryption_key: str = ""
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days
    # Probe each API key with a tiny live request at registration to reject bad
    # keys early. Disabled in tests (fake providers) and toggleable for offline use.
    registration_verify_keys: bool = True

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

    @field_validator("database_url")
    @classmethod
    def _coerce_psycopg_driver(cls, v: str) -> str:
        """Hosting platforms (Railway, Heroku, …) hand out ``postgres://`` or
        ``postgresql://`` URLs, but this app talks to Postgres through psycopg v3,
        which needs the explicit ``postgresql+psycopg://`` scheme. Rewrite so the
        platform's DATABASE_URL can be pasted in verbatim."""
        for prefix in ("postgresql+psycopg://",):
            if v.startswith(prefix):
                return v
        if v.startswith("postgresql://"):
            return "postgresql+psycopg://" + v[len("postgresql://") :]
        if v.startswith("postgres://"):
            return "postgresql+psycopg://" + v[len("postgres://") :]
        return v

    @model_validator(mode="after")
    def _require_auth_secrets_when_deployed(self) -> "Settings":
        """Fail fast: the deployed (multi-user) build cannot run safely without a
        JWT secret and an encryption master key. Catch the misconfiguration at
        startup instead of at the first login/registration."""
        if self.deployed and not (self.jwt_secret and self.secret_encryption_key):
            raise ValueError(
                "DEPLOYED=true requires JWT_SECRET and SECRET_ENCRYPTION_KEY to be "
                "set (see .env.example / RAILWAY.md)."
            )
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def effective_llm_provider(self) -> str:
        """The LLM provider actually bound. In deployed mode only Anthropic is
        offered (there is no local Ollama to run on a hosted box). When Anthropic
        is selected but no key is set, fall back to the fake LLM so the app still
        boots and the full UI loop works."""
        provider = "anthropic" if self.deployed else self.llm_provider
        if provider == "anthropic" and not self.anthropic_api_key:
            return "fake"
        return provider

    @property
    def effective_embedding_provider(self) -> str:
        """Which embedding adapter to bind, derived from deployment mode (never a
        free user choice — see `deployed`). Deployed -> Voyage AI, falling back to
        the deterministic fake provider if no Voyage key is set so the app still
        boots. Localhost -> the configured local provider (bge-m3)."""
        if self.deployed:
            return "voyage" if self.voyage_api_key else "fake"
        return self.embedding_provider

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
