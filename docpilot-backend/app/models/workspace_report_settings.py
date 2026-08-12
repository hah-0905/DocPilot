from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WorkspaceReportSettings(Base):
    """Per-workspace defaults used when creating reports."""

    __tablename__ = "workspace_report_settings"

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            name="uk_workspace_report_settings_workspace",
        ),
        CheckConstraint(
            "report_type IN ('general', 'academic_review', 'project_analysis', "
            "'contract_analysis', 'custom')",
            name="ck_workspace_report_settings_report_type",
        ),
        CheckConstraint(
            "length IN ('short', 'medium', 'long')",
            name="ck_workspace_report_settings_length",
        ),
        CheckConstraint(
            "citation_style IN ('apa', 'mla', 'chicago', 'gb_t_7714')",
            name="ck_workspace_report_settings_citation_style",
        ),
        CheckConstraint(
            "export_format IN ('pdf', 'docx', 'markdown', 'html')",
            name="ck_workspace_report_settings_export_format",
        ),
    )

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
        comment="报告设置 ID",
    )
    workspace_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "workspaces.id",
            name="fk_workspace_report_settings_workspace",
            ondelete="CASCADE",
        ),
        nullable=False,
        comment="工作空间 ID；每个工作空间仅一条设置",
    )
    report_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="general",
        server_default=text("'general'"),
        comment="默认报告类型",
    )
    length: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="medium",
        server_default=text("'medium'"),
        comment="默认报告长度：short/medium/long",
    )
    citation_style: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="apa",
        server_default=text("'apa'"),
        comment="默认引用格式",
    )
    export_format: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="markdown",
        server_default=text("'markdown'"),
        comment="默认导出格式",
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