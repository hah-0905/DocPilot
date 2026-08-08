from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, CHAR, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChunkEmbedding(Base):
    """Vector-store mapping for a document chunk embedding."""

    __tablename__ = "chunk_embeddings"

    __table_args__ = (
        UniqueConstraint("chunk_id", "embedding_model", name="uk_chunk_model"),
        UniqueConstraint(
            "vector_store_type",
            "vector_collection",
            "vector_id",
            name="uk_vector_mapping",
        ),
        Index("idx_embeddings_content_hash", "content_hash"),
        Index("idx_embeddings_kb_model", "kb_id", "embedding_model"),
        Index("idx_embeddings_status", "status"),
    )

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
        comment="Embedding ID",
    )

    kb_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("knowledge_bases.id", name="fk_chunk_embeddings_kb", ondelete="CASCADE"),
        nullable=False,
        comment="Knowledge base ID",
    )

    chunk_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("document_chunks.id", name="fk_chunk_embeddings_chunk", ondelete="CASCADE"),
        nullable=False,
        comment="Document chunk ID",
    )

    vector_store_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Vector store type",
    )

    vector_collection: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="Vector collection name",
    )

    vector_id: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        comment="Vector ID in the vector store",
    )

    embedding_model: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="Embedding model name",
    )

    embedding_dim: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Embedding vector dimension",
    )

    content_hash: Mapped[str] = mapped_column(
        CHAR(64),
        nullable=False,
        comment="Chunk content SHA256 hash",
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        server_default=text("'active'"),
        comment="Embedding status",
    )

    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        comment="Created at",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        server_onupdate=text("CURRENT_TIMESTAMP(3)"),
        comment="Updated at",
    )
