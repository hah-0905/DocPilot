from datetime import datetime
from typing import Optional

from sqlalchemy import (
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Workspace(Base):
    """
    工作空间表 ORM 模型
    """

    __tablename__ = "workspaces"

    __table_args__ = (
        Index("idx_workspaces_owner", "owner_user_id"),
        Index("idx_workspaces_status", "status"),
    )

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
        comment="工作空间ID",
    )

    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="工作空间名称",
    )

    description: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
        comment="工作空间描述",
    )

    owner_user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", name="fk_workspaces_owner"),
        nullable=False,
        comment="工作空间所有者用户ID",
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        server_default=text("'active'"),
        comment="状态：active/disabled/deleted 等",
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