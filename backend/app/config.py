"""Application settings + provider selection.

This module is half of the composition root (the other half is ``api/deps.py``).
Everything that varies by environment — which LLM/embedding/TTS adapter to bind,
model ids, the database URL, retrieval/chunking tuning — is read here from the
environment. Business logic NEVER reads env directly; it receives a ``Settings``.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    llm_provider: str = "anthropic"  # anthropic | fake
    anthropic_api_key: str = ""
    llm_model: str = "claude-haiku-4-5"
    llm_model_heavy: str = "claude-sonnet-4-6"
    llm_max_tokens: int = 1024
    # Studio artifacts (study guide, briefing, …) are long-form; a chat-sized
    # budget truncates them mid-JSON, dropping content + citations. Give Studio
    # synthesis its own, larger budget.
    studio_max_tokens: int = 4096

    # --- Embeddings provider selection ---
    embedding_provider: str = "bge_m3_local"  # bge_m3_local | fake
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024

    # --- TTS provider selection ---
    tts_provider: str = "fake"  # fake

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
