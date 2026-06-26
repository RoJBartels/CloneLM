"""users + notebook ownership (multi-user, deployed build)

Revision ID: 0002_users_and_ownership
Revises: 0001_initial
Create Date: 2026-06-26

Adds the ``app_user`` account table and a ``notebook.user_id`` owner FK. Seeds
the built-in local user (see app.shared.identity) and backfills any pre-existing
notebooks to it, so localhost keeps a single owner with no login. On a fresh
deploy DB the backfill is a no-op.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.shared.identity import LOCAL_USER_EMAIL, LOCAL_USER_ID

revision: str = "0002_users_and_ownership"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_user",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("anthropic_key_encrypted", sa.Text(), nullable=True),
        sa.Column("voyage_key_encrypted", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_app_user_email", "app_user", ["email"], unique=True)

    # Seed the built-in local user. Its password hash is a non-verifiable
    # sentinel ("!" is not a valid argon2 hash), so nobody can authenticate as it.
    op.bulk_insert(
        sa.table(
            "app_user",
            sa.column("id", postgresql.UUID(as_uuid=True)),
            sa.column("email", sa.String),
            sa.column("password_hash", sa.Text),
        ),
        [{"id": LOCAL_USER_ID, "email": LOCAL_USER_EMAIL, "password_hash": "!"}],
    )

    op.add_column(
        "notebook",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("app_user.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_notebook_user_id", "notebook", ["user_id"])

    # Backfill existing notebooks (localhost dev data) to the local user.
    op.execute(
        sa.text("UPDATE notebook SET user_id = :uid WHERE user_id IS NULL").bindparams(
            sa.bindparam("uid", LOCAL_USER_ID, type_=postgresql.UUID(as_uuid=True))
        )
    )


def downgrade() -> None:
    op.drop_index("ix_notebook_user_id", table_name="notebook")
    op.drop_column("notebook", "user_id")
    op.drop_index("ix_app_user_email", table_name="app_user")
    op.drop_table("app_user")
