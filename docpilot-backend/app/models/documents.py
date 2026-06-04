from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT, CHAR, DATETIME, MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Document(Base):
    """Uploaded document metadata."""

    __tablename__ = "documents"

    __table_args__ = (
        Index("idx_documents_kb", "kb_id"),
        Index("idx_documents_created_by", "created_by"),
        Index("idx_documents_kb_status", "kb_id", "parse_status", "index_status"),
        Index("idx_documents_sha256", "sha256"),
        Index("idx_documents_title", "title"),
    )

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
        comment="Document ID",
    )

    kb_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("knowledge_bases.id", name="fk_documents_kb", ondelete="CASCADE"),
        nullable=False,
        comment="Knowledge base ID",
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Document title",
    )

    source_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="upload",
        server_default=text("'upload'"),
        comment="Source type: upload/url/api",
    )

    source_uri: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
        comment="Source URI",
    )

    original_file_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Original file name",
    )

    file_ext: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment="File extension",
    )

    mime_type: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="MIME type",
    )

    size_bytes: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        nullable=True,
        comment="File size in bytes",
    )

    sha256: Mapped[str | None] = mapped_column(
        CHAR(64),
        nullable=True,
        comment="File SHA256 hash",
    )

    language: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment="Document language",
    )

    current_version_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        nullable=True,
        comment="Current document version ID; no DB FK to avoid cyclic DDL",
    )

    parse_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
        comment="Parse status: pending/processing/success/failed",
    )

    index_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="not_indexed",
        server_default=text("'not_indexed'"),
        comment="Index status: not_indexed/indexing/indexed/failed",
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
        comment="Whether the document is enabled",
    )

    created_by: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", name="fk_documents_created_by"),
        nullable=False,
        comment="Creator user ID",
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

    deleted_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=3),
        nullable=True,
        comment="Soft delete time",
    )


class DocumentVersion(Base):
    """Immutable file/parser version for a document."""

    __tablename__ = "document_versions"

    __table_args__ = (
        UniqueConstraint("document_id", "version_no", name="uk_document_version"),
        Index("idx_doc_versions_document", "document_id"),
        Index("idx_doc_versions_sha256", "sha256"),
        Index("idx_doc_versions_status", "status"),
    )

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
        comment="Document version ID",
    )

    document_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("documents.id", name="fk_doc_versions_document", ondelete="CASCADE"),
        nullable=False,
        comment="Document ID",
    )

    version_no: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Version number",
    )

    storage_uri: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
        comment="Stored file URI",
    )

    original_file_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Original file name",
    )

    sha256: Mapped[str | None] = mapped_column(
        CHAR(64),
        nullable=True,
        comment="File SHA256 hash",
    )

    parser_name: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="Parser name",
    )

    parser_version: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="Parser version",
    )

    parser_config: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Parser config",
    )

    page_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Page count",
    )

    char_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Character count",
    )

    token_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Token count",
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
        comment="Version status: pending/processing/success/failed",
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message",
    )

    created_by: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", name="fk_doc_versions_created_by"),
        nullable=False,
        comment="Creator user ID",
    )

    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        comment="Created at",
    )


class DocumentTag(Base):
    """Document-to-tag link. tag_id is intentionally not a DB foreign key."""

    __tablename__ = "document_tags"

    __table_args__ = (
        UniqueConstraint("document_id", "tag_id", name="uk_document_tag"),
        Index("idx_document_tags_document", "document_id"),
        Index("idx_document_tags_tag", "tag_id"),
    )

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
        comment="Document tag link ID",
    )

    document_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("documents.id", name="fk_document_tags_document", ondelete="CASCADE"),
        nullable=False,
        comment="Document ID",
    )

    tag_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        nullable=False,
        comment="Tag ID; validated in service layer",
    )

    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        comment="Created at",
    )


class DocumentChunk(Base):
    """Text chunk generated from a document version."""

    __tablename__ = "document_chunks"

    __table_args__ = (
        UniqueConstraint("chunk_uid", name="uk_chunk_uid"),
        UniqueConstraint("version_id", "chunk_no", name="uk_version_chunk_no"),
        Index("idx_chunks_kb_enabled", "kb_id", "enabled"),
        Index("idx_chunks_document", "document_id"),
        Index("idx_chunks_version", "version_id"),
        Index("idx_chunks_hash", "content_hash"),
        Index("ft_chunks_content", "content", mysql_prefix="FULLTEXT"),
    )

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
        comment="Chunk ID",
    )

    kb_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("knowledge_bases.id", name="fk_chunks_kb", ondelete="CASCADE"),
        nullable=False,
        comment="Knowledge base ID",
    )

    document_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("documents.id", name="fk_chunks_document", ondelete="CASCADE"),
        nullable=False,
        comment="Document ID",
    )

    version_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("document_versions.id", name="fk_chunks_version", ondelete="CASCADE"),
        nullable=False,
        comment="Document version ID",
    )

    chunk_no: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Chunk sequence number",
    )

    chunk_uid: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="Unique chunk identifier",
    )

    content: Mapped[str] = mapped_column(
        MEDIUMTEXT,
        nullable=False,
        comment="Chunk content",
    )

    content_hash: Mapped[str] = mapped_column(
        CHAR(64),
        nullable=False,
        comment="Chunk content SHA256 hash",
    )

    token_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Token count",
    )

    char_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Character count",
    )

    page_start: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Start page",
    )

    page_end: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="End page",
    )

    section_title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Section title",
    )

    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
        comment="Chunk metadata",
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
        comment="Whether the chunk is enabled",
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
