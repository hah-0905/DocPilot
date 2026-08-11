from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, INTEGER
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WorkspaceModelSettings(Base):
    """Per-workspace defaults used for chat and report generation."""

    __tablename__ = "workspace_model_settings"

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            name="uk_workspace_model_settings_workspace",
        ),
    )

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
        comment="模型设置 ID",
    )
    workspace_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "workspaces.id",
            name="fk_workspace_model_settings_workspace",
            ondelete="CASCADE",
        ),
        nullable=False,
        comment="工作空间 ID；每个工作空间仅一条设置",
    )
    model_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default="deepseek-chat",
        server_default=text("'deepseek-chat'"),
        comment="模型内部标识，例如 deepseek-chat 或 gpt-4o-mini",
    )
    temperature: Mapped[float] = mapped_column(
        nullable=False,
        default=0.7,
        server_default=text("0.7"),
        comment="采样温度，通常范围为 0 到 2",
    )
    max_tokens: Mapped[int] = mapped_column(
        INTEGER(unsigned=True),
        nullable=False,
        default=4096,
        server_default=text("4096"),
        comment="单次回答的最大生成 Token 数",
    )
    response_language: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="zh-CN",
        server_default=text("'zh-CN'"),
        comment="默认回复语言",
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
        server_default=text("CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"),
        comment="更新时间",
    )