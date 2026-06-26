"""SQLAlchemy implementations of the repository ports. One session per request.

These are intentionally complete (not stubs): persistence is mechanical and
shared, so feature tracks build logic on top rather than reinventing CRUD.
"""
from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

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
    User,
)
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
from app.infrastructure.persistence import orm


# --------------------------------------------------------------------------- #
# Mappers (ORM -> domain)
# --------------------------------------------------------------------------- #


def _chunk(o: orm.ChunkORM) -> Chunk:
    return Chunk(
        id=o.id,
        source_id=o.source_id,
        notebook_id=o.notebook_id,
        ordinal=o.ordinal,
        text=o.text,
        token_count=o.token_count,
        start_char=o.start_char,
        end_char=o.end_char,
        page=o.page,
        metadata=o.meta or {},
    )


def _citation(o: orm.CitationORM) -> Citation:
    return Citation(
        id=o.id,
        message_id=o.message_id,
        chunk_id=o.chunk_id or o.id,  # chunk_id is non-null in the API contract
        source_id=o.source_id,
        source_title=o.source_title,
        marker=o.marker,
        snippet=o.snippet,
        start_char=o.start_char,
        end_char=o.end_char,
        page=o.page,
    )


# --------------------------------------------------------------------------- #
# User
# --------------------------------------------------------------------------- #


def _user(o: orm.UserORM) -> User:
    return User(
        id=o.id,
        email=o.email,
        password_hash=o.password_hash,
        anthropic_key_encrypted=o.anthropic_key_encrypted,
        voyage_key_encrypted=o.voyage_key_encrypted,
        created_at=o.created_at,
    )


class SqlUserRepository(UserRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        email: str,
        password_hash: str,
        anthropic_key_encrypted: str | None,
        voyage_key_encrypted: str | None,
    ) -> User:
        o = orm.UserORM(
            email=email,
            password_hash=password_hash,
            anthropic_key_encrypted=anthropic_key_encrypted,
            voyage_key_encrypted=voyage_key_encrypted,
        )
        self.db.add(o)
        self.db.commit()
        self.db.refresh(o)
        return _user(o)

    def get(self, user_id: uuid.UUID) -> User | None:
        o = self.db.get(orm.UserORM, user_id)
        return _user(o) if o else None

    def get_by_email(self, email: str) -> User | None:
        o = self.db.scalar(select(orm.UserORM).where(orm.UserORM.email == email))
        return _user(o) if o else None

    def update_keys(
        self,
        user_id: uuid.UUID,
        *,
        anthropic_key_encrypted: str | None = None,
        voyage_key_encrypted: str | None = None,
    ) -> User | None:
        o = self.db.get(orm.UserORM, user_id)
        if not o:
            return None
        if anthropic_key_encrypted is not None:
            o.anthropic_key_encrypted = anthropic_key_encrypted
        if voyage_key_encrypted is not None:
            o.voyage_key_encrypted = voyage_key_encrypted
        self.db.commit()
        self.db.refresh(o)
        return _user(o)


# --------------------------------------------------------------------------- #
# Notebook
# --------------------------------------------------------------------------- #


class SqlNotebookRepository(NotebookRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def _to_domain(self, o: orm.NotebookORM) -> Notebook:
        source_count = self.db.scalar(
            select(func.count())
            .select_from(orm.SourceORM)
            .where(orm.SourceORM.notebook_id == o.id)
        )
        note_count = self.db.scalar(
            select(func.count())
            .select_from(orm.NoteORM)
            .where(orm.NoteORM.notebook_id == o.id)
        )
        return Notebook(
            id=o.id,
            title=o.title,
            created_at=o.created_at,
            source_count=source_count or 0,
            note_count=note_count or 0,
        )

    def create(self, title: str, *, user_id: uuid.UUID) -> Notebook:
        o = orm.NotebookORM(title=title, user_id=user_id)
        self.db.add(o)
        self.db.commit()
        self.db.refresh(o)
        return self._to_domain(o)

    def get(self, notebook_id: uuid.UUID) -> Notebook | None:
        o = self.db.get(orm.NotebookORM, notebook_id)
        return self._to_domain(o) if o else None

    def owner_id(self, notebook_id: uuid.UUID) -> uuid.UUID | None:
        return self.db.scalar(
            select(orm.NotebookORM.user_id).where(orm.NotebookORM.id == notebook_id)
        )

    def list_for_user(self, user_id: uuid.UUID) -> list[Notebook]:
        rows = self.db.scalars(
            select(orm.NotebookORM)
            .where(orm.NotebookORM.user_id == user_id)
            .order_by(orm.NotebookORM.created_at.desc())
        ).all()
        return [self._to_domain(o) for o in rows]

    def update(self, notebook_id: uuid.UUID, title: str) -> Notebook | None:
        o = self.db.get(orm.NotebookORM, notebook_id)
        if not o:
            return None
        o.title = title
        self.db.commit()
        self.db.refresh(o)
        return self._to_domain(o)

    def delete(self, notebook_id: uuid.UUID) -> bool:
        o = self.db.get(orm.NotebookORM, notebook_id)
        if not o:
            return False
        self.db.delete(o)
        self.db.commit()
        return True


# --------------------------------------------------------------------------- #
# Source
# --------------------------------------------------------------------------- #


class SqlSourceRepository(SourceRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def _to_domain(self, o: orm.SourceORM) -> Source:
        chunk_count = self.db.scalar(
            select(func.count())
            .select_from(orm.ChunkORM)
            .where(orm.ChunkORM.source_id == o.id)
        )
        return Source(
            id=o.id,
            notebook_id=o.notebook_id,
            type=SourceType(o.type),
            title=o.title,
            uri=o.uri,
            status=SourceStatus(o.status),
            error=o.error,
            chunk_count=chunk_count or 0,
            created_at=o.created_at,
        )

    def create(
        self,
        *,
        notebook_id: uuid.UUID,
        type: SourceType,
        title: str,
        uri: str | None = None,
    ) -> Source:
        o = orm.SourceORM(
            notebook_id=notebook_id,
            type=type.value,
            title=title,
            uri=uri,
            status=SourceStatus.processing.value,
        )
        self.db.add(o)
        self.db.commit()
        self.db.refresh(o)
        return self._to_domain(o)

    def get(self, source_id: uuid.UUID) -> Source | None:
        o = self.db.get(orm.SourceORM, source_id)
        return self._to_domain(o) if o else None

    def list_for_notebook(self, notebook_id: uuid.UUID) -> list[Source]:
        rows = self.db.scalars(
            select(orm.SourceORM)
            .where(orm.SourceORM.notebook_id == notebook_id)
            .order_by(orm.SourceORM.created_at.asc())
        ).all()
        return [self._to_domain(o) for o in rows]

    def set_status(
        self, source_id: uuid.UUID, status: SourceStatus, error: str | None = None
    ) -> None:
        o = self.db.get(orm.SourceORM, source_id)
        if not o:
            return
        o.status = status.value
        o.error = error
        self.db.commit()

    def delete(self, source_id: uuid.UUID) -> bool:
        o = self.db.get(orm.SourceORM, source_id)
        if not o:
            return False
        self.db.delete(o)
        self.db.commit()
        return True


# --------------------------------------------------------------------------- #
# Chunk
# --------------------------------------------------------------------------- #


class SqlChunkRepository(ChunkRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def add_many(
        self, chunks: list[Chunk], embeddings: list[list[float]], embedding_model: str
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings length mismatch")
        for ch, emb in zip(chunks, embeddings):
            self.db.add(
                orm.ChunkORM(
                    id=ch.id,
                    source_id=ch.source_id,
                    notebook_id=ch.notebook_id,
                    ordinal=ch.ordinal,
                    text=ch.text,
                    token_count=ch.token_count,
                    start_char=ch.start_char,
                    end_char=ch.end_char,
                    page=ch.page,
                    meta=ch.metadata,
                    embedding=emb,
                    embedding_model=embedding_model,
                )
            )
        self.db.commit()

    def get(self, chunk_id: uuid.UUID) -> Chunk | None:
        o = self.db.get(orm.ChunkORM, chunk_id)
        return _chunk(o) if o else None

    def get_many(self, chunk_ids: list[uuid.UUID]) -> list[Chunk]:
        if not chunk_ids:
            return []
        rows = self.db.scalars(
            select(orm.ChunkORM).where(orm.ChunkORM.id.in_(chunk_ids))
        ).all()
        return [_chunk(o) for o in rows]

    def list_for_source(self, source_id: uuid.UUID) -> list[Chunk]:
        rows = self.db.scalars(
            select(orm.ChunkORM)
            .where(orm.ChunkORM.source_id == source_id)
            .order_by(orm.ChunkORM.ordinal.asc())
        ).all()
        return [_chunk(o) for o in rows]

    def count_for_source(self, source_id: uuid.UUID) -> int:
        return self.db.scalar(
            select(func.count())
            .select_from(orm.ChunkORM)
            .where(orm.ChunkORM.source_id == source_id)
        ) or 0

    def delete_for_source(self, source_id: uuid.UUID) -> None:
        self.db.execute(delete(orm.ChunkORM).where(orm.ChunkORM.source_id == source_id))
        self.db.commit()


# --------------------------------------------------------------------------- #
# Conversation & Message
# --------------------------------------------------------------------------- #


class SqlConversationRepository(ConversationRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, notebook_id: uuid.UUID) -> Conversation:
        o = orm.ConversationORM(notebook_id=notebook_id)
        self.db.add(o)
        self.db.commit()
        self.db.refresh(o)
        return Conversation(id=o.id, notebook_id=o.notebook_id, created_at=o.created_at)

    def get(self, conversation_id: uuid.UUID) -> Conversation | None:
        o = self.db.get(orm.ConversationORM, conversation_id)
        return (
            Conversation(id=o.id, notebook_id=o.notebook_id, created_at=o.created_at)
            if o
            else None
        )

    def list_for_notebook(self, notebook_id: uuid.UUID) -> list[Conversation]:
        rows = self.db.scalars(
            select(orm.ConversationORM)
            .where(orm.ConversationORM.notebook_id == notebook_id)
            .order_by(orm.ConversationORM.created_at.asc())
        ).all()
        return [
            Conversation(id=o.id, notebook_id=o.notebook_id, created_at=o.created_at)
            for o in rows
        ]


class SqlMessageRepository(MessageRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def _to_domain(self, o: orm.MessageORM) -> Message:
        return Message(
            id=o.id,
            conversation_id=o.conversation_id,
            role=MessageRole(o.role),
            content=o.content,
            citations=[_citation(c) for c in o.citations],
            created_at=o.created_at,
        )

    def add(
        self,
        *,
        conversation_id: uuid.UUID,
        role: MessageRole,
        content: str,
        citations: list[CitationDraft] | None = None,
    ) -> Message:
        o = orm.MessageORM(
            conversation_id=conversation_id, role=role.value, content=content
        )
        self.db.add(o)
        self.db.flush()  # assign o.id before attaching citations
        for c in citations or []:
            self.db.add(
                orm.CitationORM(
                    message_id=o.id,
                    chunk_id=c.chunk_id,
                    source_id=c.source_id,
                    source_title=c.source_title,
                    marker=c.marker,
                    snippet=c.snippet,
                    start_char=c.start_char,
                    end_char=c.end_char,
                    page=c.page,
                )
            )
        self.db.commit()
        self.db.refresh(o)
        return self._to_domain(o)

    def get(self, message_id: uuid.UUID) -> Message | None:
        o = self.db.get(orm.MessageORM, message_id)
        return self._to_domain(o) if o else None

    def list_for_conversation(self, conversation_id: uuid.UUID) -> list[Message]:
        rows = self.db.scalars(
            select(orm.MessageORM)
            .where(orm.MessageORM.conversation_id == conversation_id)
            .order_by(orm.MessageORM.created_at.asc())
        ).all()
        return [self._to_domain(o) for o in rows]

    def list_citations(self, message_id: uuid.UUID) -> list[Citation]:
        rows = self.db.scalars(
            select(orm.CitationORM).where(orm.CitationORM.message_id == message_id)
        ).all()
        return [_citation(o) for o in rows]


# --------------------------------------------------------------------------- #
# Note
# --------------------------------------------------------------------------- #


class SqlNoteRepository(NoteRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def _to_domain(self, o: orm.NoteORM) -> Note:
        return Note(
            id=o.id,
            notebook_id=o.notebook_id,
            title=o.title,
            content=o.content,
            origin=NoteOrigin(o.origin),
            created_at=o.created_at,
            updated_at=o.updated_at,
        )

    def create(
        self, *, notebook_id: uuid.UUID, title: str, content: str, origin: NoteOrigin
    ) -> Note:
        o = orm.NoteORM(
            notebook_id=notebook_id, title=title, content=content, origin=origin.value
        )
        self.db.add(o)
        self.db.commit()
        self.db.refresh(o)
        return self._to_domain(o)

    def get(self, note_id: uuid.UUID) -> Note | None:
        o = self.db.get(orm.NoteORM, note_id)
        return self._to_domain(o) if o else None

    def list_for_notebook(self, notebook_id: uuid.UUID) -> list[Note]:
        rows = self.db.scalars(
            select(orm.NoteORM)
            .where(orm.NoteORM.notebook_id == notebook_id)
            .order_by(orm.NoteORM.updated_at.desc())
        ).all()
        return [self._to_domain(o) for o in rows]

    def update(
        self, note_id: uuid.UUID, *, title: str | None = None, content: str | None = None
    ) -> Note | None:
        o = self.db.get(orm.NoteORM, note_id)
        if not o:
            return None
        if title is not None:
            o.title = title
        if content is not None:
            o.content = content
        self.db.commit()
        self.db.refresh(o)
        return self._to_domain(o)

    def delete(self, note_id: uuid.UUID) -> bool:
        o = self.db.get(orm.NoteORM, note_id)
        if not o:
            return False
        self.db.delete(o)
        self.db.commit()
        return True


# --------------------------------------------------------------------------- #
# Studio output
# --------------------------------------------------------------------------- #


class SqlStudioOutputRepository(StudioOutputRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def _to_domain(self, o: orm.StudioOutputORM) -> StudioOutput:
        return StudioOutput(
            id=o.id,
            notebook_id=o.notebook_id,
            kind=StudioKind(o.kind),
            title=o.title,
            content=o.content,
            citations=[_citation(c) for c in o.citations],
            created_at=o.created_at,
        )

    def create(
        self,
        *,
        notebook_id: uuid.UUID,
        kind: StudioKind,
        title: str,
        content: str,
        citations: list[CitationDraft] | None = None,
    ) -> StudioOutput:
        o = orm.StudioOutputORM(
            notebook_id=notebook_id, kind=kind.value, title=title, content=content
        )
        self.db.add(o)
        self.db.flush()
        for c in citations or []:
            self.db.add(
                orm.CitationORM(
                    studio_output_id=o.id,
                    chunk_id=c.chunk_id,
                    source_id=c.source_id,
                    source_title=c.source_title,
                    marker=c.marker,
                    snippet=c.snippet,
                    start_char=c.start_char,
                    end_char=c.end_char,
                    page=c.page,
                )
            )
        self.db.commit()
        self.db.refresh(o)
        return self._to_domain(o)

    def get(self, output_id: uuid.UUID) -> StudioOutput | None:
        o = self.db.get(orm.StudioOutputORM, output_id)
        return self._to_domain(o) if o else None

    def list_for_notebook(self, notebook_id: uuid.UUID) -> list[StudioOutput]:
        rows = self.db.scalars(
            select(orm.StudioOutputORM)
            .where(orm.StudioOutputORM.notebook_id == notebook_id)
            .order_by(orm.StudioOutputORM.created_at.desc())
        ).all()
        return [self._to_domain(o) for o in rows]


# --------------------------------------------------------------------------- #
# Audio
# --------------------------------------------------------------------------- #


class SqlAudioRepository(AudioRepository):
    def __init__(self, db: Session) -> None:
        self.db = db

    def _to_domain(self, o: orm.AudioOverviewORM) -> AudioOverview:
        return AudioOverview(
            id=o.id,
            notebook_id=o.notebook_id,
            status=AudioStatus(o.status),
            url=o.url,
            created_at=o.created_at,
        )

    def create(self, notebook_id: uuid.UUID) -> AudioOverview:
        o = orm.AudioOverviewORM(
            notebook_id=notebook_id, status=AudioStatus.processing.value
        )
        self.db.add(o)
        self.db.commit()
        self.db.refresh(o)
        return self._to_domain(o)

    def get(self, audio_id: uuid.UUID) -> AudioOverview | None:
        o = self.db.get(orm.AudioOverviewORM, audio_id)
        return self._to_domain(o) if o else None

    def list_for_notebook(self, notebook_id: uuid.UUID) -> list[AudioOverview]:
        rows = self.db.scalars(
            select(orm.AudioOverviewORM)
            .where(orm.AudioOverviewORM.notebook_id == notebook_id)
            .order_by(orm.AudioOverviewORM.created_at.desc())
        ).all()
        return [self._to_domain(o) for o in rows]

    def set_status(
        self, audio_id: uuid.UUID, status: AudioStatus, url: str | None = None
    ) -> None:
        o = self.db.get(orm.AudioOverviewORM, audio_id)
        if not o:
            return
        o.status = status.value
        if url is not None:
            o.url = url
        self.db.commit()
