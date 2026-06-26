"""Composition root: bind ports -> concrete adapters, selected from env config.

This is the ONLY module (with ``config.py``) allowed to import infrastructure
adapters and decide which one implements each port. Routers and services depend
on these provider functions via FastAPI's ``Depends`` — never on a concrete
class directly.
"""
from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from functools import lru_cache

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.models import User
from app.domain.ports.auth import PasswordHasher, SecretCipher, TokenService
from app.domain.ports.embeddings import EmbeddingProvider
from app.domain.ports.llm import LLMMessage, LLMProvider
from app.domain.ports.repositories import (
    AudioRepository,
    ChunkRepository,
    ConversationRepository,
    MessageRepository,
    NoteRepository,
    NotebookRepository,
    SourceRepository,
    StudioOutputRepository,
    UserRepository,
)
from app.domain.ports.tts import TTSProvider
from app.domain.ports.vector_store import VectorStore
from app.infrastructure.persistence.db import get_sessionmaker
from app.infrastructure.persistence.pgvector_store import PgVectorStore
from app.infrastructure.persistence.repositories import (
    SqlAudioRepository,
    SqlChunkRepository,
    SqlConversationRepository,
    SqlMessageRepository,
    SqlNoteRepository,
    SqlNotebookRepository,
    SqlSourceRepository,
    SqlStudioOutputRepository,
    SqlUserRepository,
)
from app.infrastructure.providers.anthropic_llm import AnthropicLLMProvider
from app.infrastructure.providers.bge_embeddings import BgeM3EmbeddingProvider
from app.infrastructure.providers.fake_embeddings import FakeEmbeddingProvider
from app.infrastructure.providers.voyage_embeddings import VoyageEmbeddingProvider
from app.infrastructure.providers.fake_llm import FakeLLMProvider
from app.infrastructure.providers.ollama_llm import OllamaLLMProvider
from app.infrastructure.providers.fake_tts import FakeTTSProvider
from app.infrastructure.providers.piper_tts import PiperTTSProvider
from app.infrastructure.security import (
    Argon2PasswordHasher,
    FernetCipher,
    JwtTokenService,
)
from app.shared.identity import LOCAL_USER_EMAIL, LOCAL_USER_ID
from app.shared.logging import get_logger

log = get_logger(__name__)

# --------------------------------------------------------------------------- #
# Database session (one per request)
# --------------------------------------------------------------------------- #


def get_db() -> Iterator[Session]:
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()


# --------------------------------------------------------------------------- #
# Provider singletons (bind port -> adapter from config)
# --------------------------------------------------------------------------- #


@lru_cache
def get_llm() -> LLMProvider:
    s = get_settings()
    if s.effective_llm_provider == "anthropic":
        return AnthropicLLMProvider(
            api_key=s.anthropic_api_key,
            model=s.llm_model,
            heavy_model=s.llm_model_heavy,
            default_max_tokens=s.llm_max_tokens,
        )
    if s.effective_llm_provider == "ollama":
        return OllamaLLMProvider(
            base_url=s.ollama_base_url,
            model=s.ollama_model,
            heavy_model=s.ollama_model_heavy,
            default_max_tokens=s.llm_max_tokens,
        )
    return FakeLLMProvider()


def ollama_available(base_url: str) -> bool:
    """Liveness probe for a local Ollama server (used by the settings UI)."""
    return OllamaLLMProvider(base_url=base_url).is_available()


def rebind_llm() -> None:
    """Drop the cached LLM provider so the next request re-reads config and
    binds the newly selected provider/model (used after a settings change)."""
    get_llm.cache_clear()


@lru_cache
def get_embedder() -> EmbeddingProvider:
    s = get_settings()
    # The provider is derived from deployment mode, not a free config choice, so
    # a notebook's vectors are always produced by one embedding model.
    provider = s.effective_embedding_provider
    if provider == "voyage":
        return VoyageEmbeddingProvider(
            api_key=s.voyage_api_key, model=s.voyage_model, dim=s.embedding_dim
        )
    if provider == "bge_m3_local":
        return BgeM3EmbeddingProvider(model_name=s.embedding_model, dim=s.embedding_dim)
    return FakeEmbeddingProvider(dim=s.embedding_dim)


@lru_cache
def get_tts() -> TTSProvider:
    s = get_settings()
    if s.tts_provider == "piper":
        provider = PiperTTSProvider(
            voice_dir=s.piper_voice_dir,
            voice_host_a=s.piper_voice_host_a,
            voice_host_b=s.piper_voice_host_b,
            output_sample_rate=s.piper_sample_rate,
        )
        if provider.is_available():
            return provider
        # Degrade gracefully (silent placeholder) rather than break the audio
        # endpoint when the 'audio' extra isn't installed.
        log.warning(
            "Piper TTS selected but the 'audio' extra is not installed; "
            "falling back to silent fake TTS. Install with `uv sync --extra audio`."
        )
    return FakeTTSProvider()


def get_vector_store(db: Session = Depends(get_db)) -> VectorStore:
    return PgVectorStore(db)


# --------------------------------------------------------------------------- #
# Auth: hasher / token / cipher singletons + the current-user dependency
# --------------------------------------------------------------------------- #


@lru_cache
def get_password_hasher() -> PasswordHasher:
    return Argon2PasswordHasher()


@lru_cache
def get_token_service() -> TokenService:
    s = get_settings()
    return JwtTokenService(secret=s.jwt_secret, expire_minutes=s.jwt_expire_minutes)


@lru_cache
def get_cipher() -> SecretCipher:
    return FernetCipher(master_key=get_settings().secret_encryption_key)


def get_user_repo(db: Session = Depends(get_db)) -> UserRepository:
    return SqlUserRepository(db)


def _bearer_token(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def get_current_user(
    authorization: str | None = Header(default=None),
    user_repo: UserRepository = Depends(get_user_repo),
    token_service: TokenService = Depends(get_token_service),
) -> User:
    """Resolve the request's user. Localhost (DEPLOYED=false) has no login and
    resolves to the seeded local user, so authorization is uniform in both modes.
    Deployed requires a valid bearer token."""
    s = get_settings()
    if not s.deployed:
        return User(
            id=LOCAL_USER_ID,
            email=LOCAL_USER_EMAIL,
            password_hash="!",
            created_at=datetime.now(timezone.utc),
        )

    token = _bearer_token(authorization)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    user_id = token_service.verify(token)
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = user_repo.get(user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer exists")
    return user


def get_user_llm(
    user: User = Depends(get_current_user),
    local_llm: LLMProvider = Depends(get_llm),
) -> LLMProvider:
    """The LLM bound to the current user. Localhost reuses the env-configured
    provider (``local_llm``, taken via Depends so test overrides still apply);
    deployed builds an Anthropic provider from the user's own decrypted key."""
    s = get_settings()
    if not s.deployed:
        return local_llm
    if not user.anthropic_key_encrypted:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "No Anthropic API key on file. Add one in Einstellungen.",
        )
    api_key = get_cipher().decrypt(user.anthropic_key_encrypted)
    return AnthropicLLMProvider(
        api_key=api_key,
        model=s.llm_model,
        heavy_model=s.llm_model_heavy,
        default_max_tokens=s.llm_max_tokens,
    )


def get_user_embedder(
    user: User = Depends(get_current_user),
    local_embedder: EmbeddingProvider = Depends(get_embedder),
) -> EmbeddingProvider:
    """The embedder bound to the current user. Localhost reuses the cached local
    bge-m3 (``local_embedder``, via Depends so test overrides still apply);
    deployed builds a Voyage provider from the user's own decrypted key."""
    s = get_settings()
    if not s.deployed:
        return local_embedder
    if not user.voyage_key_encrypted:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "No Voyage API key on file. Add one in Einstellungen.",
        )
    api_key = get_cipher().decrypt(user.voyage_key_encrypted)
    return VoyageEmbeddingProvider(
        api_key=api_key, model=s.voyage_model, dim=s.embedding_dim
    )


def probe_user_keys(anthropic_key: str, voyage_key: str) -> None:
    """Best-effort live validation of a user's API keys at registration. Each is
    exercised with a tiny real request through its provider port, so a typo/dead
    key is rejected up front rather than failing later mid-chat. Raises
    HTTPException(422) on rejection; toggle off via REGISTRATION_VERIFY_KEYS."""
    s = get_settings()
    try:
        AnthropicLLMProvider(api_key=anthropic_key, model=s.llm_model).complete(
            [LLMMessage(role="user", content="ping")], max_tokens=1
        )
    except Exception as exc:  # noqa: BLE001 - any failure -> reject the key
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"Anthropic API key rejected: {exc}"
        ) from exc
    try:
        VoyageEmbeddingProvider(
            api_key=voyage_key, model=s.voyage_model, dim=s.embedding_dim
        ).embed_query("ping")
    except Exception as exc:  # noqa: BLE001 - any failure -> reject the key
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"Voyage API key rejected: {exc}"
        ) from exc


def assert_notebook_owner(
    notebook_repo: NotebookRepository, notebook_id: uuid.UUID, user: User
) -> None:
    """Gate access to a notebook. Deployed: 404 unless the user owns it — 404
    (not 403) so other users' notebooks don't leak by existence. Localhost is
    single-tenant, so it only enforces existence (ownership is moot). Routes call
    this directly (they already inject ``notebook_repo`` + ``user``)."""
    if get_settings().deployed:
        if notebook_repo.owner_id(notebook_id) != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Notebook not found")
    elif notebook_repo.get(notebook_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notebook not found")


# --------------------------------------------------------------------------- #
# Repository factories (per request, bound to the request's session)
# --------------------------------------------------------------------------- #


def get_notebook_repo(db: Session = Depends(get_db)) -> NotebookRepository:
    return SqlNotebookRepository(db)


def get_source_repo(db: Session = Depends(get_db)) -> SourceRepository:
    return SqlSourceRepository(db)


def get_chunk_repo(db: Session = Depends(get_db)) -> ChunkRepository:
    return SqlChunkRepository(db)


def get_conversation_repo(db: Session = Depends(get_db)) -> ConversationRepository:
    return SqlConversationRepository(db)


def get_message_repo(db: Session = Depends(get_db)) -> MessageRepository:
    return SqlMessageRepository(db)


def get_note_repo(db: Session = Depends(get_db)) -> NoteRepository:
    return SqlNoteRepository(db)


def get_studio_repo(db: Session = Depends(get_db)) -> StudioOutputRepository:
    return SqlStudioOutputRepository(db)


def get_audio_repo(db: Session = Depends(get_db)) -> AudioRepository:
    return SqlAudioRepository(db)
