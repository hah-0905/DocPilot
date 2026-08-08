import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.document_task_cache_service import (
    DocumentTaskCacheService,
)
from app.db.session import AsyncSessional
from app.models.document_processing_tasks import DocumentProcessingTask


logger = logging.getLogger(__name__)


def utc_now_naive() -> datetime:
    """
    返回不携带时区信息的 UTC 时间。

    项目使用 MySQL DATETIME，因此在写入前移除 tzinfo。
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DocumentTaskService:
    """文档处理任务的创建、更新和查询服务。"""

    def __init__(self) -> None:
        self.cache_service = DocumentTaskCacheService()
    
    
    async def cache_task_by_id(
        self,
        task_id: str,
        *,
        force_latest: bool = True,
    ) -> bool:
        '''
        缓存任务。
        '''
        async with AsyncSessional() as db:
            result = await db.execute(
                select(DocumentProcessingTask).where(
                    DocumentProcessingTask.task_id == task_id
                )
            )
            task = result.scalar_one_or_none()
    
            if task is None:
                logger.error(
                    "Cannot cache missing task: task_id=%s",
                    task_id,
                )
                return False
    
            return await self.cache_service.write_task(
                task,
                force_latest=force_latest,
            )

    async def create_task(
        self,
        db: AsyncSession,
        *,
        kb_id: int,
        document_id: int,
        version_id: int,
        created_by: int,
    ) -> DocumentProcessingTask:
        """
        创建 queued/uploaded 状态的文档处理任务。

        本方法不主动 commit，由调用方与 Document、DocumentVersion
        一起提交，保证三条记录同时创建成功。
        """
        task = DocumentProcessingTask(
            task_id=str(uuid.uuid4()),
            kb_id=kb_id,
            document_id=document_id,
            version_id=version_id,
            created_by=created_by,
            status="queued",
            stage="uploaded",
            progress=0,
            total_chunks=0,
            processed_chunks=0,
            failed_chunks=0,
            retry_count=0,
            max_retries=3,
        )

        db.add(task)
        await db.flush()
        return task

    async def update_task(
        self,
        task_id: str,
        **values: Any,
    ) -> bool:
        '''
        更新文档处理任务。
        '''
        allowed_fields = {
            "status",
            "stage",
            "progress",
            "total_chunks",
            "processed_chunks",
            "failed_chunks",
            "retry_count",
            "max_retries",
            "error_code",
            "error_message",
            "started_at",
            "completed_at",
        }

        invalid_fields = set(values) - allowed_fields
        if invalid_fields:
            raise ValueError(
                "Unsupported task update fields: "
                f"{sorted(invalid_fields)}"
            )

        if "progress" in values:
            values["progress"] = max(
                0,
                min(100, int(values["progress"])),
            )

        try:
            async with AsyncSessional() as db:
                result = await db.execute(
                    select(DocumentProcessingTask).where(
                        DocumentProcessingTask.task_id
                        == task_id
                    )
                )
                task = result.scalar_one_or_none()

                if task is None:
                    logger.error(
                        "Document task not found: task_id=%s",
                        task_id,
                    )
                    return False

                for field, value in values.items():
                    setattr(task, field, value)

                task.updated_at = utc_now_naive()

                # MySQL 先提交
                await db.commit()
                await db.refresh(task)

                # Redis 写入失败不回滚 MySQL
                cache_updated = (
                    await self.cache_service.write_task(
                        task,
                        force_latest=False,
                    )
                )

                if not cache_updated:
                    logger.warning(
                        "Task updated in MySQL but Redis cache "
                        "update failed: task_id=%s",
                        task_id,
                    )

                return True

        except Exception:
            logger.exception(
                "Failed to update document task: "
                "task_id=%s, values=%s",
                task_id,
                values,
            )
            return False

    async def mark_running(
        self,
        task_id: str,
        *,
        stage: str,
        progress: int,
    ) -> bool:
        '''
        标记任务正在运行。
        '''
        return await self.update_task(
            task_id,
            status="running",
            stage=stage,
            progress=progress,
            started_at=utc_now_naive(),
            error_code=None,
            error_message=None,
        )

    async def update_progress(
        self,
        task_id: str,
        *,
        stage: str,
        progress: int,
        total_chunks: int | None = None,
        processed_chunks: int | None = None,
        failed_chunks: int | None = None,
    ) -> bool:
        '''
        更新任务进度。
        '''
        values: dict[str, Any] = {
            "status": "running",
            "stage": stage,
            "progress": progress,
        }

        if total_chunks is not None:
            values["total_chunks"] = total_chunks

        if processed_chunks is not None:
            values["processed_chunks"] = processed_chunks

        if failed_chunks is not None:
            values["failed_chunks"] = failed_chunks

        return await self.update_task(task_id, **values)

    async def mark_success(
        self,
        task_id: str,
        *,
        total_chunks: int,
    ) -> bool:
        '''
        标记任务成功。
        '''
        return await self.update_task(
            task_id,
            status="success",
            stage="completed",
            progress=100,
            total_chunks=total_chunks,
            processed_chunks=total_chunks,
            failed_chunks=0,
            error_code=None,
            error_message=None,
            completed_at=utc_now_naive(),
        )

    async def mark_failed(
        self,
        task_id: str,
        *,
        stage: str,
        error_code: str,
        error_message: str,
    ) -> bool:
        '''
        标记任务失败。
        '''
        return await self.update_task(
            task_id,
            status="failed",
            stage=stage,
            error_code=error_code,
            error_message=error_message[:4000],
            completed_at=utc_now_naive(),
        )

    async def get_latest_task(
        self,
        db: AsyncSession,
        *,
        kb_id: int,
        document_id: int,
    ) -> DocumentProcessingTask | None:
        '''
        获取最新的任务。
        '''
        result = await db.execute(
            select(DocumentProcessingTask)
            .where(
                DocumentProcessingTask.kb_id == kb_id,
                DocumentProcessingTask.document_id == document_id,
            )
            .order_by(
                DocumentProcessingTask.created_at.desc(),
                DocumentProcessingTask.id.desc(),
            )
            .limit(1)
        )

        return result.scalar_one_or_none()


    async def get_latest_task_status(
        self,
        db: AsyncSession,
        *,
        kb_id: int,
        document_id: int,
    ) -> dict[str, Any] | None:
        """
        Redis 优先，MySQL 回退。
    
        Redis 缓存未命中时，从 MySQL 读取并回填 Redis。
        """
        latest_task_id = (
            await self.cache_service.get_latest_task_id(
                kb_id=kb_id,
                document_id=document_id,
            )
        )
    
        if latest_task_id:
            cached_task = await self.cache_service.get_task(
                latest_task_id
            )
    
            if (
                cached_task is not None
                and cached_task["kb_id"] == kb_id
                and cached_task["document_id"] == document_id
            ):
                cached_task["cache_source"] = "redis"
                return cached_task
    
        task = await self.get_latest_task(
            db=db,
            kb_id=kb_id,
            document_id=document_id,
        )
    
        if task is None:
            return None
    
        await self.cache_service.write_task(
            task,
            force_latest=True,
        )
    
        result = self.cache_service.task_to_dict(task)
        result["heartbeat_at"] = None
        result["stale"] = False
        result["cache_source"] = "mysql"
        return result