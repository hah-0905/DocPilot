from datetime import datetime

from sqlalchemy import (
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WorkspaceMember(Base):
    """
    工作空间成员表 ORM 模型
    """

    __tablename__ = "workspace_members"

    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uk_workspace_user"),
        Index("idx_workspace_members_role", "workspace_id", "role"),
        Index("idx_workspace_members_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
        comment="工作空间成员ID",
    )

    workspace_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "workspaces.id",
            name="fk_workspace_members_workspace",
            ondelete="CASCADE",
        ),
        nullable=False,
        comment="工作空间ID",
    )

    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "users.id",
            name="fk_workspace_members_user",
            ondelete="CASCADE",
        ),
        nullable=False,
        comment="用户ID",
    )

    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="member",
        server_default=text("'member'"),
        comment="成员角色：owner/admin/member 等",
    )

    joined_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        comment="加入时间",
    )