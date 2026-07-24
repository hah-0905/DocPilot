
from pathlib import Path
import re
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.report import ReportExport, ReportTask
from app.core.config import get_settings
from app.core.storage import path_in_directory


class ReportExportService:

    @staticmethod
    def _save_file_name(
        title: str
    ) -> str:
        """
        清理 Windows 和 Linux 文件名中的非法字符。
        """
        cleaned = re.sub(r'[\\/:*?"<>|]', '_', title).strip()
        return cleaned[:100] or "report"

    async def create_markdown_export(
        self,
        db: AsyncSession,
        task_id: int,
        user_id: int,
    ) -> ReportExport:
        # 只能导出当前用户自己的报告
        result = await db.execute(
            select(ReportTask)
            .where(
                ReportTask.id == task_id,
                ReportTask.user_id == user_id,
            )
        )

        task = result.scalar_one_or_none()

        if not task:  # 找不到报告
            raise HTTPException(
                status_code=404,
                detail="报告不存在"
            )

        if not task.result_content:  # 报告内容为空
            raise HTTPException(
                status_code=400,
                detail="报告内容为空"
            )

        export_root = Path(get_settings().export_dir).expanduser().resolve()
        export_dir = export_root / str(user_id) / str(task_id)
        export_dir.mkdir(parents=True, exist_ok=True)

        safe_title = self._save_file_name(task.title)
        unique_suffix = uuid4().hex[:8]

        file_name = f"{safe_title}_{unique_suffix}.md"
        file_path = path_in_directory(export_root, export_dir / file_name)

        file_path.write_text(
            task.result_content,
            encoding="utf-8",
        )

        export = ReportExport(
            task_id=task.id,
            export_format="markdown",
            storage_uri=str(file_path),
            file_name=file_name,
            size_bytes=file_path.stat().st_size,
            status="success",
        )

        db.add(export)
        await db.commit()
        await db.refresh(export)

        return export

    async def get_export_for_download(
        self,
        db: AsyncSession,
        export_id: int,
        user_id: int,
    ) -> ReportExport:
        result = await db.execute(
            select(ReportExport)
            .join(
                ReportTask,
                ReportTask.id == ReportExport.task_id,
            )
            .where(
                ReportExport.id == export_id,
                ReportTask.user_id == user_id,
            )
        )

        export = result.scalar_one_or_none()

        if export is None:
            raise HTTPException(
                status_code=404,
                detail="导出记录不存在或无权访问",
            )

        return export

    async def get_task_exports(
        self,
        db: AsyncSession,
        task_id: int,
        user_id: int,
    ) -> list[ReportExport]:
        result = await db.execute(
            select(ReportExport)
            .join(
                ReportTask,
                ReportTask.id == ReportExport.task_id,
            )
            .where(
                ReportExport.task_id == task_id,
                ReportTask.user_id == user_id,
            )
            .order_by(ReportExport.created_at.desc())
        )

        return list(result.scalars().all())
