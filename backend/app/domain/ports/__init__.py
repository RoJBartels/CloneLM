"""Port interfaces (hexagonal boundary). Import ports from here:

    from app.domain.ports import LLMProvider, EmbeddingProvider, VectorStore
"""
from app.domain.ports.embeddings import EmbeddingProvider
from app.domain.ports.llm import LLMMessage, LLMProvider, LLMResponse, LLMUsage
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
from app.domain.ports.tts import TTSProvider, TTSSegment
from app.domain.ports.vector_store import VectorStore

__all__ = [
    "EmbeddingProvider",
    "LLMProvider",
    "LLMMessage",
    "LLMResponse",
    "LLMUsage",
    "TTSProvider",
    "TTSSegment",
    "VectorStore",
    "NotebookRepository",
    "SourceRepository",
    "ChunkRepository",
    "ConversationRepository",
    "MessageRepository",
    "NoteRepository",
    "StudioOutputRepository",
    "AudioRepository",
]
