from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, JSON, LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReportTask(Base):
    """Report generation task."""

    __tablename__ = "report_tasks"

    __table_args__ = (
        Index("idx_report_tasks_status", "status"),
        Index("idx_report_tasks_user", "user_id", "created_at"),
        Index("idx_report_tasks_workspace", "workspace_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
        comment="Report task ID",
    )

    workspace_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("workspaces.id", name="fk_report_tasks_workspace", ondelete="CASCADE"),
        nullable=False,
        comment="Workspace ID",
    )

    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", name="fk_report_tasks_user", ondelete="CASCADE"),
        nullable=False,
        comment="User ID",
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Report title",
    )

    report_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="general",
        server_default=text("'general'"),
        comment="Report type",
    )

    instruction: Mapped[str | None] = mapped_column(
        LONGTEXT,
        nullable=True,
        comment="Report generation instruction",
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
        comment="Task status",
    )

    model_name: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="LLM model name",
    )

    config: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Task config",
    )

    result_content: Mapped[str | None] = mapped_column(
        LONGTEXT,
        nullable=True,
        comment="Generated report content",
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message",
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=3),
        nullable=True,
        comment="Started at",
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=3),
        nullable=True,
        comment="Finished at",
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


class ReportSection(Base):
    """Section generated for a report task."""

    __tablename__ = "report_sections"

    __table_args__ = (
        UniqueConstraint("task_id", "order_no", name="uk_report_section_order"),
        Index("idx_report_sections_parent", "parent_section_id"),
        Index("idx_report_sections_status", "task_id", "status"),
    )

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
        comment="Report section ID",
    )

    task_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("report_tasks.id", name="fk_report_sections_task", ondelete="CASCADE"),
        nullable=False,
        comment="Report task ID",
    )

    parent_section_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("report_sections.id", name="fk_report_sections_parent", ondelete="SET NULL"),
        nullable=True,
        comment="Parent section ID",
    )

    order_no: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Section order number",
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Section title",
    )

    requirement: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Section requirement",
    )

    content: Mapped[str | None] = mapped_column(
        LONGTEXT,
        nullable=True,
        comment="Section content",
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
        comment="Section status",
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


class ReportSource(Base):
    """Source citation used by a report task or section."""

    __tablename__ = "report_sources"

    __table_args__ = (
        Index("idx_report_sources_chunk", "chunk_id"),
        Index("idx_report_sources_section", "section_id"),
        Index("idx_report_sources_task", "task_id"),
    )

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
        comment="Report source ID",
    )

    task_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("report_tasks.id", name="fk_report_sources_task", ondelete="CASCADE"),
        nullable=False,
        comment="Report task ID",
    )

    section_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("report_sections.id", name="fk_report_sources_section", ondelete="SET NULL"),
        nullable=True,
        comment="Report section ID",
    )

    kb_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("knowledge_bases.id", name="fk_report_sources_kb", ondelete="CASCADE"),
        nullable=False,
        comment="Knowledge base ID",
    )

    document_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("documents.id", name="fk_report_sources_document", ondelete="CASCADE"),
        nullable=False,
        comment="Document ID",
    )

    chunk_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("document_chunks.id", name="fk_report_sources_chunk", ondelete="CASCADE"),
        nullable=False,
        comment="Document chunk ID",
    )

    citation_no: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Citation number",
    )

    quote_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Quoted text",
    )

    score: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 6),
        nullable=True,
        comment="Retrieval score",
    )

    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        comment="Created at",
    )


class ReportExport(Base):
    """Exported file for a report task."""

    __tablename__ = "report_exports"

    __table_args__ = (
        Index("idx_report_exports_format", "export_format"),
        Index("idx_report_exports_task", "task_id"),
    )

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
        comment="Report export ID",
    )

    task_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("report_tasks.id", name="fk_report_exports_task", ondelete="CASCADE"),
        nullable=False,
        comment="Report task ID",
    )

    export_format: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="Export format",
    )

    storage_uri: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        comment="Storage URI",
    )

    file_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="File name",
    )

    size_bytes: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        nullable=True,
        comment="File size in bytes",
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="success",
        server_default=text("'success'"),
        comment="Export status",
    )

    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        comment="Created at",
    )
