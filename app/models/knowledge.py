"""Knowledge base models: Parent-Child Indexing for RAG."""

import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DocType(str, enum.Enum):
    STATUTE = "statute"
    DMC = "dmc"
    CIRCULAR = "circular"
    INTERNAL = "internal"
    COURT_CASE = "court_case"
    GUIDELINE = "guideline"


class ParentDoc(Base):
    """Large context chunks (1000-1500 tokens) containing full sections/articles."""

    __tablename__ = "parent_docs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), index=True
    )
    content: Mapped[str] = mapped_column(Text)
    doc_type: Mapped[DocType] = mapped_column(
        Enum(DocType, values_callable=lambda e: [m.value for m in e])
    )
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    # TSVector for hybrid search (semantic + keyword)
    search_vector = Column(TSVECTOR)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    children: Mapped[list["ChildChunk"]] = relationship(back_populates="parent")

    __table_args__ = (
        # GIN index on TSVector for fast full-text search
        Index("ix_parent_docs_search_vector", "search_vector", postgresql_using="gin"),
    )


class ChildChunk(Base):
    """Small indexed units (200-300 tokens) with vector embeddings."""

    __tablename__ = "child_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    parent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("parent_docs.id", ondelete="CASCADE"), index=True
    )
    # BGE-M3 produces 1024-dimensional vectors
    embedding = Column(Vector(1024))
    language: Mapped[str] = mapped_column(String(10))  # zh_hk, en
    search_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    parent: Mapped["ParentDoc"] = relationship(back_populates="children")

    __table_args__ = (
        # HNSW index for fast approximate nearest-neighbor vector search
        Index(
            "ix_child_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
