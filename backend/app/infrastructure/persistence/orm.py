"""SQLAlchemy ORM models — the physical schema. Mirrored by the single initial
Alembic migration (kept in sync by hand; do not autogenerate over it without
review). The embedding vector dimension is config-driven but the migration fixes
it; changing it requires a re-embed + dimension migration (see CLAUDE.md)."""
from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import get_settings
from app.infrastructure.persistence.db import Base

_EMBEDDING_DIM = get_settings().embedding_dim


def _uuid_col() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class UserORM(Base):
    """Account row for the deployed (multi-user) build. ``password_hash`` is a
    one-way argon2id hash; the API keys are Fernet-encrypted at rest (the server
    holds no plaintext key). Table is ``app_user`` to avoid the reserved word
    ``user`` in Postgres."""

    __tablename__ = "app_user"

    id: Mapped[uuid.UUID] = _uuid_col()
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    anthropic_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    voyage_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=func.now()
    )


class NotebookORM(Base):
    __tablename__ = "notebook"

    id: Mapped[uuid.UUID] = _uuid_col()
    # Owner. Nullable for migration safety on pre-existing local data; the app
    # always sets it (real user when deployed, the seeded local user otherwise).
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("app_user.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=func.now()
    )

    sources: Mapped[list["SourceORM"]] = relationship(
        back_populates="notebook", cascade="all, delete-orphan"
    )
    notes: Mapped[list["NoteORM"]] = relationship(
        back_populates="notebook", cascade="all, delete-orphan"
    )


class SourceORM(Base):
    __tablename__ = "source"

    id: Mapped[uuid.UUID] = _uuid_col()
    notebook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notebook.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="processing")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    chunk_strategy: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=func.now()
    )

    notebook: Mapped[NotebookORM] = relationship(back_populates="sources")
    chunks: Mapped[list["ChunkORM"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class ChunkORM(Base):
    __tablename__ = "chunk"

    id: Mapped[uuid.UUID] = _uuid_col()
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source.id", ondelete="CASCADE"), index=True
    )
    notebook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notebook.id", ondelete="CASCADE"), index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    start_char: Mapped[int] = mapped_column(Integer, default=0)
    end_char: Mapped[int] = mapped_column(Integer, default=0)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    meta: Mapped[dict] = mapped_column("meta", JSONB, default=dict)
    embedding = mapped_column(Vector(_EMBEDDING_DIM), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=func.now()
    )

    source: Mapped[SourceORM] = relationship(back_populates="chunks")


class ConversationORM(Base):
    __tablename__ = "conversation"

    id: Mapped[uuid.UUID] = _uuid_col()
    notebook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notebook.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=func.now()
    )

    messages: Mapped[list["MessageORM"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class MessageORM(Base):
    __tablename__ = "message"

    id: Mapped[uuid.UUID] = _uuid_col()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversation.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=func.now()
    )

    conversation: Mapped[ConversationORM] = relationship(back_populates="messages")
    citations: Mapped[list["CitationORM"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )


class CitationORM(Base):
    """Generic citation row: belongs to either a message or a studio output.
    Source fields are denormalized so a citation renders even if the underlying
    chunk is later re-indexed."""

    __tablename__ = "citation"

    id: Mapped[uuid.UUID] = _uuid_col()
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("message.id", ondelete="CASCADE"), nullable=True
    )
    studio_output_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("studio_output.id", ondelete="CASCADE"),
        nullable=True,
    )
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chunk.id", ondelete="SET NULL"), nullable=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_title: Mapped[str] = mapped_column(String(500), nullable=False)
    marker: Mapped[int] = mapped_column(Integer, nullable=False)
    snippet: Mapped[str] = mapped_column(Text, nullable=False, default="")
    start_char: Mapped[int] = mapped_column(Integer, default=0)
    end_char: Mapped[int] = mapped_column(Integer, default=0)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=func.now()
    )

    message: Mapped[MessageORM | None] = relationship(back_populates="citations")


class NoteORM(Base):
    __tablename__ = "note"

    id: Mapped[uuid.UUID] = _uuid_col()
    notebook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notebook.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    origin: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=func.now(),
        onupdate=func.now(),
    )

    notebook: Mapped[NotebookORM] = relationship(back_populates="notes")


class StudioOutputORM(Base):
    __tablename__ = "studio_output"

    id: Mapped[uuid.UUID] = _uuid_col()
    notebook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notebook.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=func.now()
    )

    citations: Mapped[list[CitationORM]] = relationship(
        cascade="all, delete-orphan",
        primaryjoin="StudioOutputORM.id == CitationORM.studio_output_id",
    )


class AudioOverviewORM(Base):
    __tablename__ = "audio_overview"

    id: Mapped[uuid.UUID] = _uuid_col()
    notebook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notebook.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="processing")
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    script: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=func.now()
    )
