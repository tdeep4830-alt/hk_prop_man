"""Initial core schema — all tables from data_structure.md.

Revision ID: 001
Revises: None
Create Date: 2026-02-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Extensions ---
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, index=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column(
            "membership_tier",
            sa.Enum("free", "pro", "enterprise", name="membershiptier"),
            server_default="free",
            nullable=False,
        ),
        sa.Column("pref_lang", sa.String(10), server_default="zh_hk", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- user_identities ---
    op.create_table(
        "user_identities",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_uid", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- parent_docs ---
    op.create_table(
        "parent_docs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("property_id", UUID(as_uuid=True), index=True, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "doc_type",
            sa.Enum("statute", "dmc", "circular", "internal", name="doctype"),
            nullable=False,
        ),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("search_vector", TSVECTOR),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # GIN index for full-text search
    op.create_index(
        "ix_parent_docs_search_vector",
        "parent_docs",
        ["search_vector"],
        postgresql_using="gin",
    )

    # --- child_chunks ---
    op.create_table(
        "child_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "parent_id",
            UUID(as_uuid=True),
            sa.ForeignKey("parent_docs.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
        sa.Column("embedding", Vector(1024)),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("search_text", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # HNSW index for vector similarity search (cosine)
    op.create_index(
        "ix_child_chunks_embedding_hnsw",
        "child_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    # --- conversations ---
    op.create_table(
        "conversations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
        sa.Column(
            "platform",
            sa.Enum("web", "telegram", name="platform"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- messages ---
    op.create_table(
        "messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conv_id",
            UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.Enum("user", "assistant", "system", name="messagerole"),
            nullable=False,
        ),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("citations", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- usage_quotas ---
    op.create_table(
        "usage_quotas",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
        ),
        sa.Column("quota_date", sa.Date, nullable=False),
        sa.Column("llm_calls_count", sa.Integer, server_default="0", nullable=False),
    )

    # --- audit_logs ---
    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("detail", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("usage_quotas")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_index("ix_child_chunks_embedding_hnsw", table_name="child_chunks")
    op.drop_table("child_chunks")
    op.drop_index("ix_parent_docs_search_vector", table_name="parent_docs")
    op.drop_table("parent_docs")
    op.drop_table("user_identities")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS membershiptier")
    op.execute("DROP TYPE IF EXISTS doctype")
    op.execute("DROP TYPE IF EXISTS platform")
    op.execute("DROP TYPE IF EXISTS messagerole")
