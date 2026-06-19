"""Repository ports — persistence interfaces for each aggregate.

Services depend on these abstractions; the SQLAlchemy implementations live in
``infrastructure/persistence/repositories.py``. Method sets are part of the
frozen Phase-0 contract so feature tracks don't have to add migrations or
re-shape repositories mid-sprint.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from app.domain.models import (
    AudioOverview,
    AudioStatus,
    Chunk,
    Citation,
    CitationDraft,
    Conversation,
    Message,
    MessageRole,
    Note,
    NoteOrigin,
    Notebook,
    Source,
    SourceStatus,
    SourceType,
    StudioKind,
    StudioOutput,
)


class NotebookRepository(ABC):
    @abstractmethod
    def create(self, title: str) -> Notebook: ...

    @abstractmethod
    def get(self, notebook_id: uuid.UUID) -> Notebook | None: ...

    @abstractmethod
    def list(self) -> list[Notebook]: ...

    @abstractmethod
    def update(self, notebook_id: uuid.UUID, title: str) -> Notebook | None: ...

    @abstractmethod
    def delete(self, notebook_id: uuid.UUID) -> bool: ...


class SourceRepository(ABC):
    @abstractmethod
    def create(
        self,
        *,
        notebook_id: uuid.UUID,
        type: SourceType,
        title: str,
        uri: str | None = None,
    ) -> Source: ...

    @abstractmethod
    def get(self, source_id: uuid.UUID) -> Source | None: ...

    @abstractmethod
    def list_for_notebook(self, notebook_id: uuid.UUID) -> list[Source]: ...

    @abstractmethod
    def set_status(
        self, source_id: uuid.UUID, status: SourceStatus, error: str | None = None
    ) -> None: ...

    @abstractmethod
    def delete(self, source_id: uuid.UUID) -> bool: ...


class ChunkRepository(ABC):
    @abstractmethod
    def add_many(
        self, chunks: list[Chunk], embeddings: list[list[float]], embedding_model: str
    ) -> None:
        """Persist chunks together with their vectors. ``chunks[i]`` pairs with
        ``embeddings[i]``."""

    @abstractmethod
    def get(self, chunk_id: uuid.UUID) -> Chunk | None: ...

    @abstractmethod
    def get_many(self, chunk_ids: list[uuid.UUID]) -> list[Chunk]: ...

    @abstractmethod
    def list_for_source(self, source_id: uuid.UUID) -> list[Chunk]: ...

    @abstractmethod
    def count_for_source(self, source_id: uuid.UUID) -> int: ...

    @abstractmethod
    def delete_for_source(self, source_id: uuid.UUID) -> None: ...


class ConversationRepository(ABC):
    @abstractmethod
    def create(self, notebook_id: uuid.UUID) -> Conversation: ...

    @abstractmethod
    def get(self, conversation_id: uuid.UUID) -> Conversation | None: ...

    @abstractmethod
    def list_for_notebook(self, notebook_id: uuid.UUID) -> list[Conversation]: ...


class MessageRepository(ABC):
    @abstractmethod
    def add(
        self,
        *,
        conversation_id: uuid.UUID,
        role: MessageRole,
        content: str,
        citations: list[CitationDraft] | None = None,
    ) -> Message:
        """Persist a message and (for assistant turns) its citations atomically."""

    @abstractmethod
    def get(self, message_id: uuid.UUID) -> Message | None: ...

    @abstractmethod
    def list_for_conversation(self, conversation_id: uuid.UUID) -> list[Message]: ...

    @abstractmethod
    def list_citations(self, message_id: uuid.UUID) -> list[Citation]: ...


class NoteRepository(ABC):
    @abstractmethod
    def create(
        self,
        *,
        notebook_id: uuid.UUID,
        title: str,
        content: str,
        origin: NoteOrigin,
    ) -> Note: ...

    @abstractmethod
    def get(self, note_id: uuid.UUID) -> Note | None: ...

    @abstractmethod
    def list_for_notebook(self, notebook_id: uuid.UUID) -> list[Note]: ...

    @abstractmethod
    def update(
        self, note_id: uuid.UUID, *, title: str | None = None, content: str | None = None
    ) -> Note | None: ...

    @abstractmethod
    def delete(self, note_id: uuid.UUID) -> bool: ...


class StudioOutputRepository(ABC):
    @abstractmethod
    def create(
        self,
        *,
        notebook_id: uuid.UUID,
        kind: StudioKind,
        title: str,
        content: str,
        citations: list[CitationDraft] | None = None,
    ) -> StudioOutput: ...

    @abstractmethod
    def get(self, output_id: uuid.UUID) -> StudioOutput | None: ...

    @abstractmethod
    def list_for_notebook(self, notebook_id: uuid.UUID) -> list[StudioOutput]: ...


class AudioRepository(ABC):
    @abstractmethod
    def create(self, notebook_id: uuid.UUID) -> AudioOverview: ...

    @abstractmethod
    def get(self, audio_id: uuid.UUID) -> AudioOverview | None: ...

    @abstractmethod
    def list_for_notebook(self, notebook_id: uuid.UUID) -> list[AudioOverview]: ...

    @abstractmethod
    def set_status(
        self, audio_id: uuid.UUID, status: AudioStatus, url: str | None = None
    ) -> None: ...
