from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, JSON, LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChatSession(Base):
    """
    聊天会话表 ORM 模型
    """

    __tablename__ = "chat_sessions"

    __table_args__ = (
        Index("idx_chat_sessions_status", "status"),
        Index("idx_chat_sessions_user", "user_id", "created_at"),
        Index("idx_chat_sessions_workspace", "workspace_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
        comment="聊天会话ID",
    )

    workspace_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("workspaces.id", name="fk_chat_sessions_workspace", ondelete="CASCADE"),
        nullable=False,
        comment="工作空间ID",
    )

    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", name="fk_chat_sessions_user", ondelete="CASCADE"),
        nullable=False,
        comment="用户ID",
    )

    title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="会话标题",
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        server_default=text("'active'"),
        comment="状态：active/deleted 等",
    )

    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        comment="创建时间",
    )


class ChatSessionKb(Base):
    """
    聊天会话知识库关联表 ORM 模型
    """

    __tablename__ = "chat_session_kbs"

    __table_args__ = (
        UniqueConstraint("session_id", "kb_id", name="uk_session_kb"),
        Index("idx_chat_session_kbs_kb", "kb_id"),
    )

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
        comment="会话知识库关联ID",
    )

    session_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("chat_sessions.id", name="fk_chat_session_kbs_session", ondelete="CASCADE"),
        nullable=False,
        comment="聊天会话ID",
    )

    kb_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("knowledge_bases.id", name="fk_chat_session_kbs_kb", ondelete="CASCADE"),
        nullable=False,
        comment="知识库ID",
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


class ChatMessage(Base):
    """
    聊天消息表 ORM 模型
    """

    __tablename__ = "chat_messages"

    __table_args__ = (
        Index("idx_chat_messages_parent", "parent_message_id"),
        Index("idx_chat_messages_role", "role"),
        Index("idx_chat_messages_session_created", "session_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
        comment="聊天消息ID",
    )

    session_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("chat_sessions.id", name="fk_chat_messages_session", ondelete="CASCADE"),
        nullable=False,
        comment="聊天会话ID",
    )

    parent_message_id: Mapped[Optional[int]] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("chat_messages.id", name="fk_chat_messages_parent", ondelete="SET NULL"),
        nullable=True,
        comment="父消息ID",
    )

    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="消息角色：system/user/assistant/tool 等",
    )

    content: Mapped[str] = mapped_column(
        LONGTEXT,
        nullable=False,
        comment="消息内容",
    )

    model_name: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        comment="模型名称",
    )

    prompt_tokens: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="提示词 token 数",
    )

    completion_tokens: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="生成 token 数",
    )

    total_tokens: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="总 token 数",
    )

    latency_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="响应耗时（毫秒）",
    )

    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
        comment="消息元数据",
    )

    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        comment="创建时间",
    )
