"""initial schema — full data model + pgvector

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-19

The ENTIRE initial schema lives in this one migration (PLAN.md merge-safety
rule) so feature tracks rarely add migrations early. The embedding vector is
fixed at 1024 dims (bge-m3). Changing the embedding model's dimension requires a
new migration + re-embed (see CLAUDE.md "Updatability note").
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 1024


def _uuid_pk() -> sa.Column:
    return sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True)


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )


def _notebook_fk() -> sa.Column:
    return sa.Column(
        "notebook_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("notebook.id", ondelete="CASCADE"),
        nullable=False,
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "notebook",
        _uuid_pk(),
        sa.Column("title", sa.String(200), nullable=False),
        _created_at(),
    )

    op.create_table(
        "source",
        _uuid_pk(),
        _notebook_fk(),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("uri", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="processing"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("embedding_model", sa.String(128), nullable=True),
        sa.Column("chunk_strategy", sa.String(64), nullable=True),
        _created_at(),
    )
    op.create_index("ix_source_notebook_id", "source", ["notebook_id"])

    op.create_table(
        "chunk",
        _uuid_pk(),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("source.id", ondelete="CASCADE"),
            nullable=False,
        ),
        _notebook_fk(),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("start_char", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("end_char", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("meta", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("embedding_model", sa.String(128), nullable=True),
        _created_at(),
    )
    op.create_index("ix_chunk_source_id", "chunk", ["source_id"])
    op.create_index("ix_chunk_notebook_id", "chunk", ["notebook_id"])
    # Approximate-NN index for cosine similarity search.
    op.create_index(
        "ix_chunk_embedding_hnsw",
        "chunk",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    op.create_table(
        "conversation",
        _uuid_pk(),
        _notebook_fk(),
        _created_at(),
    )
    op.create_index("ix_conversation_notebook_id", "conversation", ["notebook_id"])

    op.create_table(
        "message",
        _uuid_pk(),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversation.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        _created_at(),
    )
    op.create_index("ix_message_conversation_id", "message", ["conversation_id"])

    op.create_table(
        "studio_output",
        _uuid_pk(),
        _notebook_fk(),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        _created_at(),
    )
    op.create_index("ix_studio_output_notebook_id", "studio_output", ["notebook_id"])

    op.create_table(
        "citation",
        _uuid_pk(),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("message.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "studio_output_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("studio_output.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "chunk_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chunk.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_title", sa.String(500), nullable=False),
        sa.Column("marker", sa.Integer(), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=False, server_default=""),
        sa.Column("start_char", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("end_char", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("page", sa.Integer(), nullable=True),
        _created_at(),
    )
    op.create_index("ix_citation_message_id", "citation", ["message_id"])
    op.create_index("ix_citation_studio_output_id", "citation", ["studio_output_id"])

    op.create_table(
        "note",
        _uuid_pk(),
        _notebook_fk(),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("origin", sa.String(16), nullable=False, server_default="manual"),
        _created_at(),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_note_notebook_id", "note", ["notebook_id"])

    op.create_table(
        "audio_overview",
        _uuid_pk(),
        _notebook_fk(),
        sa.Column("status", sa.String(16), nullable=False, server_default="processing"),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("script", sa.Text(), nullable=True),
        _created_at(),
    )
    op.create_index("ix_audio_overview_notebook_id", "audio_overview", ["notebook_id"])


def downgrade() -> None:
    for table in (
        "audio_overview",
        "note",
        "citation",
        "studio_output",
        "message",
        "conversation",
        "chunk",
        "source",
        "notebook",
    ):
        op.drop_table(table)
