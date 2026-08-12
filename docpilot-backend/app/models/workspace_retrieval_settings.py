from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, INTEGER, TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WorkspaceRetrievalSettings(Base):
    """Per-workspace defaults used for knowledge-base retrieval."""

    __tablename__ = "workspace_retrieval_settings"

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            name="uk_workspace_retrieval_settings_workspace",
        ),
        CheckConstraint(
            "top_k BETWEEN 1 AND 50",
            name="ck_workspace_retrieval_settings_top_k",
        ),
        CheckConstraint(
            "similarity_threshold BETWEEN 0 AND 1",
            name="ck_workspace_retrieval_settings_similarity_threshold",
        ),
    )

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
        comment="检索设置 ID",
    )
    workspace_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "workspaces.id",
            name="fk_workspace_retrieval_settings_workspace",
            ondelete="CASCADE",
        ),
        nullable=False,
        comment="工作空间 ID；每个工作空间仅一条设置",
    )
    top_k: Mapped[int] = mapped_column(
        INTEGER(unsigned=True),
        nullable=False,
        default=10,
        server_default=text("10"),
        comment="每次检索返回的候选文档数量",
    )
    similarity_threshold: Mapped[float] = mapped_column(
        nullable=False,
        default=0.65,
        server_default=text("0.65"),
        comment="相似度过滤阈值，范围为 0 到 1",
    )
    enable_rerank: Mapped[bool] = mapped_column(
        TINYINT(1),
        nullable=False,
        default=True,
        server_default=text("1"),
        comment="是否启用重排序",
    )
    show_sources: Mapped[bool] = mapped_column(
        TINYINT(1),
        nullable=False,
        default=True,
        server_default=text("1"),
        comment="回答中是否展示引用来源",
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