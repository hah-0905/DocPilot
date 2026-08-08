from datetime import datetime

from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT, CHAR, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DocumentProcessingTask(Base):
    """文档解析、切分、Embedding 和向量入库任务。"""

    __tablename__ = "document_processing_tasks"

    __table_args__ = (
        UniqueConstraint(
            "task_id",
            name="uk_document_processing_tasks_task_id",
        ),
        Index(
            "idx_document_processing_tasks_document",
            "document_id",
        ),
        Index(
            "idx_document_processing_tasks_kb_status",
            "kb_id",
            "status",
        ),
        Index(
            "idx_document_processing_tasks_status_stage",
            "status",
            "stage",
        ),
        Index(
            "idx_document_processing_tasks_created_at",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
        comment="任务数据库主键",
    )

    task_id: Mapped[str] = mapped_column(
        CHAR(36),
        nullable=False,
        comment="对外暴露的任务 UUID",
    )

    kb_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "knowledge_bases.id",
            name="fk_document_processing_tasks_kb",
            ondelete="CASCADE",
        ),
        nullable=False,
        comment="知识库 ID",
    )

    document_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "documents.id",
            name="fk_document_processing_tasks_document",
            ondelete="CASCADE",
        ),
        nullable=False,
        comment="文档 ID",
    )

    version_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "document_versions.id",
            name="fk_document_processing_tasks_version",
            ondelete="CASCADE",
        ),
        nullable=False,
        comment="文档版本 ID",
    )

    created_by: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "users.id",
            name="fk_document_processing_tasks_created_by",
        ),
        nullable=False,
        comment="任务创建用户 ID",
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="queued",
        server_default=text("'queued'"),
        comment="queued/running/success/failed/cancelled",
    )

    stage: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="uploaded",
        server_default=text("'uploaded'"),
        comment=(
            "uploaded/parsing/splitting/embedding/"
            "vector_upserting/finalizing/completed"
        ),
    )

    progress: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="处理进度，范围 0-100",
    )

    total_chunks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Chunk 总数",
    )

    processed_chunks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="已完成向量入库的 Chunk 数",
    )

    failed_chunks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="处理失败的 Chunk 数",
    )

    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="已重试次数",
    )

    max_retries: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        server_default=text("3"),
        comment="最大重试次数",
    )

    error_code: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="业务错误码",
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="任务失败信息",
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=3),
        nullable=True,
        comment="任务开始时间",
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DATETIME(fsp=3),
        nullable=True,
        comment="任务完成时间",
    )

    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        comment="任务创建时间",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        server_onupdate=text("CURRENT_TIMESTAMP(3)"),
        comment="任务更新时间",
    )
