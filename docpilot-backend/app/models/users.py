from datetime import datetime
from typing import Optional
from app.db.base import Base
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy import (
    BigInteger,
    String,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT, CHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship


class User(Base):
    """
    用户信息表ORM模型
    """

    __tablename__ = "users"

    # 创建索引：提升查询速度 → 添加目录
    __table_args__ = (
        UniqueConstraint("email", name="uk_users_email"),
        UniqueConstraint("username", name="uk_users_username"),
    )

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True, comment="用户ID")
    username: Mapped[str] = mapped_column(
        String(64),    nullable=False,    comment="用户名",)
    email: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="邮箱",)
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="密码哈希",)
    display_name: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, comment="显示名称",)
    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True, comment="头像URL",)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'active'"), comment="用户状态",)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DATETIME(fsp=3), nullable=True, comment="最后登录时间",)
    created_at: Mapped[datetime] = mapped_column(DATETIME(
        fsp=3), nullable=False, server_default=text("CURRENT_TIMESTAMP(3)"), comment="创建时间",)
    updated_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False, server_default=text(
        "CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3)"), comment="更新时间",)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DATETIME(fsp=3), nullable=True, comment="软删除时间",)
    auth_action_tokens: Mapped[list["AuthActionToken"]] = relationship(
        "AuthActionToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class AuthActionToken(Base):
    """
    用户操作Token表ORM模型

    用于：
    1. 邮箱验证 email_verify
    2. 密码重置 password_reset
    3. 修改邮箱 change_email
    """

    __tablename__ = "auth_action_tokens"

    __table_args__ = (
        UniqueConstraint("token_hash", name="uk_auth_action_tokens_hash"),

        Index("idx_auth_action_tokens_user", "user_id"),
        Index("idx_auth_action_tokens_action", "action_type"),
        Index("idx_auth_action_tokens_expires_at", "expires_at"),
        Index("idx_auth_action_tokens_used_at", "used_at"),
    )

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
        comment="操作Token ID",
    )

    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="用户ID",
    )

    token_hash: Mapped[str] = mapped_column(
        CHAR(64),
        nullable=False,
        comment="Token哈希值，建议存sha256结果",
    )

    action_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="操作类型：email_verify / password_reset / change_email",
    )

    target: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="目标值，例如待验证的新邮箱",
    )

    expires_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3),
        nullable=False,
        comment="过期时间",
    )

    used_at: Mapped[Optional[datetime]] = mapped_column(
        DATETIME(fsp=3),
        nullable=True,
        comment="使用时间",
    )

    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(3)"),
        comment="创建时间",
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="auth_action_tokens",
    )
