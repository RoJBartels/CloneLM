"""Composition root: bind ports -> concrete adapters, selected from env config.

This is the ONLY module (with ``config.py``) allowed to import infrastructure
adapters and decide which one implements each port. Routers and services depend
on these provider functions via FastAPI's ``Depends`` — never on a concrete
class directly.
"""
from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.ports.embeddings import EmbeddingProvider
from app.domain.ports.llm import LLMProvider
from app.domain.ports.repositories import (
    AudioRepository,
    ChunkRepository,
    ConversationRepository,
    MessageRepository,
    NoteRepository,
    NotebookRepository,
    SourceRepository,
    StudioOutputRepository,
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
)
from app.infrastructure.providers.anthropic_llm import AnthropicLLMProvider
from app.infrastructure.providers.bge_embeddings import BgeM3EmbeddingProvider
from app.infrastructure.providers.fake_embeddings import FakeEmbeddingProvider
from app.infrastructure.providers.fake_llm import FakeLLMProvider
from app.infrastructure.providers.fake_tts import FakeTTSProvider

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
    return FakeLLMProvider()


@lru_cache
def get_embedder() -> EmbeddingProvider:
    s = get_settings()
    if s.embedding_provider == "bge_m3_local":
        return BgeM3EmbeddingProvider(model_name=s.embedding_model, dim=s.embedding_dim)
    return FakeEmbeddingProvider(dim=s.embedding_dim)


@lru_cache
def get_tts() -> TTSProvider:
    # Only a fake adapter exists today; real TTS is the stretch (Track F).
    return FakeTTSProvider()


def get_vector_store(db: Session = Depends(get_db)) -> VectorStore:
    return PgVectorStore(db)


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
