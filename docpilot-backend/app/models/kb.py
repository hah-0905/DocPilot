from datetime import datetime
from typing import Optional

from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class KnowledgeBase(Base):
    """
    知识库表 ORM 模型
    """

    __tablename__ = "knowledge_bases"

    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uk_workspace_kb_name"),
        Index("idx_kb_created_by", "created_by"),
        Index("idx_kb_workspace_status", "workspace_id", "status"),
    )

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
        comment="知识库ID",
    )

    workspace_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("workspaces.id", name="fk_kb_workspace", ondelete="CASCADE"),
        nullable=False,
        comment="工作空间ID",
    )

    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="知识库名称",
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="知识库描述",
    )

    visibility: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="private",
        server_default=text("'private'"),
        comment="可见性：private/public 等",
    )

    embedding_model: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        comment="向量嵌入模型",
    )

    rerank_model: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        comment="重排序模型",
    )

    chunk_strategy: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="recursive",
        server_default=text("'recursive'"),
        comment="分块策略",
    )

    chunk_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=800,
        server_default=text("800"),
        comment="分块大小",
    )

    chunk_overlap: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100,
        server_default=text("100"),
        comment="分块重叠大小",
    )

    default_top_k: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
        server_default=text("5"),
        comment="默认召回数量",
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        server_default=text("'active'"),
        comment="状态：active/disabled/deleted 等",
    )

    created_by: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", name="fk_kb_created_by"),
        nullable=False,
        comment="创建者用户ID",
    )

    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        comment="创建时间",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        server_onupdate=text("CURRENT_TIMESTAMP(3)"),
        comment="更新时间",
    )

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DATETIME(fsp=3),
        nullable=True,
        comment="软删除时间",
    )