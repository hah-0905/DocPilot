import logging
from datetime import datetime, timezone
from typing import Any

from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.redis import get_redis_client
from app.models.document_processing_tasks import DocumentProcessingTask


logger = logging.getLogger(__name__)


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DocumentTaskCacheService:
    """文档任务 Redis 缓存服务。"""

    TERMINAL_STATUSES = {
        "success",
        "failed",
        "cancelled",
    }

    INTEGER_FIELDS = {
        "kb_id",
        "document_id",
        "version_id",
        "created_by",
        "progress",
        "total_chunks",
        "processed_chunks",
        "failed_chunks",
        "retry_count",
        "max_retries",
    }

    def __init__(self) -> None:
        self.settings = get_settings()

    @staticmethod
    def task_key(task_id: str) -> str:
        '''
        获取任务 Redis 键。
        '''
        return f"docpilot:document:task:{task_id}"

    @staticmethod
    def latest_task_key(
        kb_id: int,
        document_id: int,
    ) -> str:
        '''
        获取文档最新任务 ID 的 Redis 键。
        '''
        return (
            "docpilot:document:latest-task:"
            f"{kb_id}:{document_id}"
        )

    @staticmethod
    def _datetime_to_string(
        value: datetime | None,
    ) -> str:
        '''
        将 datetime 对象转换为 ISO 格式字符串。
        如果值为 None，则返回空字符串。
        '''
        if value is None:
            return ""

        return value.isoformat()

    def task_to_dict(
        self,
        task: DocumentProcessingTask,
    ) -> dict[str, Any]:
        """将 ORM 对象转换为 API 可返回的数据。"""
        return {
            "task_id": task.task_id,
            "kb_id": task.kb_id,
            "document_id": task.document_id,
            "version_id": task.version_id,
            "created_by": task.created_by,
            "status": task.status,
            "stage": task.stage,
            "progress": task.progress,
            "total_chunks": task.total_chunks,
            "processed_chunks": task.processed_chunks,
            "failed_chunks": task.failed_chunks,
            "retry_count": task.retry_count,
            "max_retries": task.max_retries,
            "error_code": task.error_code,
            "error_message": task.error_message,
            "started_at": self._datetime_to_string(
                task.started_at
            ) or None,
            "completed_at": self._datetime_to_string(
                task.completed_at
            ) or None,
            "created_at": self._datetime_to_string(
                task.created_at
            ) or None,
            "updated_at": self._datetime_to_string(
                task.updated_at
            ) or None,
        }

    def _task_to_redis_mapping(
        self,
        task: DocumentProcessingTask,
    ) -> dict[str, str]:
        '''
        将任务对象转换为 Redis 哈希映射。
        '''
        data = self.task_to_dict(task)

        mapping = {
            key: "" if value is None else str(value)
            for key, value in data.items()
        }

        mapping["heartbeat_at"] = (
            utc_now_naive().isoformat()
        )

        return mapping

    def _deserialize(
        self,
        data: dict[str, str],
    ) -> dict[str, Any]:
        '''
        将 Redis 中的哈希数据反序列化为字典。
        '''
        result: dict[str, Any] = dict(data)

        for field in self.INTEGER_FIELDS:
            value = result.get(field)

            if value not in (None, ""):
                result[field] = int(value)
            else:
                result[field] = 0

        for field in {
            "error_code",
            "error_message",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
            "heartbeat_at",
        }:
            if result.get(field) == "":
                result[field] = None

        result["stale"] = self._is_stale(result)
        return result

    def _is_stale(
        self,
        data: dict[str, Any],
    ) -> bool:
        """
        判断运行中任务是否长时间没有更新心跳。

        这里只返回 stale 标记，不自动把任务改为 failed。
        """
        if data.get("status") != "running":
            return False

        heartbeat_at = data.get("heartbeat_at")
        if not heartbeat_at:
            return True

        try:
            heartbeat_time = datetime.fromisoformat(
                heartbeat_at
            )
        except ValueError:
            return True

        age_seconds = (
            utc_now_naive() - heartbeat_time
        ).total_seconds()

        return (
            age_seconds
            > self.settings.document_task_heartbeat_timeout_seconds
        )

    def _get_ttl(
        self,
        status: str,
    ) -> int:
        '''
        根据任务状态获取缓存过期时间
        '''
        if status in self.TERMINAL_STATUSES:
            return (
                self.settings
                .document_task_terminal_ttl_seconds
            )

        return (
            self.settings
            .document_task_active_ttl_seconds
        )

    async def write_task(
        self,
        task: DocumentProcessingTask,
        *,
        force_latest: bool = False,
    ) -> bool:
        """
        写入任务状态。

        force_latest=True 用于新任务创建，强制更新文档最新任务映射。
        普通进度更新不会覆盖其他新任务的 latest-task 映射。
        """
        client = get_redis_client()
        if client is None:
            return False

        task_key = self.task_key(task.task_id)
        latest_key = self.latest_task_key(
            task.kb_id,
            task.document_id,
        )
        ttl = self._get_ttl(task.status)
        mapping = self._task_to_redis_mapping(task)

        try:
            update_latest = force_latest

            if not force_latest:
                current_latest = await client.get(
                    latest_key
                )

                update_latest = (
                    current_latest is None
                    or current_latest == task.task_id
                )

            pipeline = client.pipeline(
                transaction=True
            )

            for field, value in mapping.items():
                pipeline.hset(
                    task_key,
                    field,
                    value,
                )
            pipeline.expire(
                task_key,
                ttl,
            )

            if update_latest:
                pipeline.set(
                    latest_key,
                    task.task_id,
                    ex=ttl,
                )

            await pipeline.execute()
            return True

        except RedisError:
            logger.exception(
                "Failed to write task cache: task_id=%s",
                task.task_id,
            )
            return False

    async def get_task(
        self,
        task_id: str,
    ) -> dict[str, Any] | None:
        '''
        获取任务状态
        '''
        client = get_redis_client()
        if client is None:
            return None

        try:
            data = await client.hgetall(
                self.task_key(task_id)
            )
        except RedisError:
            logger.exception(
                "Failed to read task cache: task_id=%s",
                task_id,
            )
            return None

        if not data:
            return None

        return self._deserialize(data)

    async def get_latest_task_id(
        self,
        *,
        kb_id: int,
        document_id: int,
    ) -> str | None:
        '''
        获取文档最新任务 ID
        '''
        client = get_redis_client()
        if client is None:
            return None

        try:
            return await client.get(
                self.latest_task_key(
                    kb_id,
                    document_id,
                )
            )
        except RedisError:
            logger.exception(
                "Failed to read latest task mapping: "
                "kb_id=%s, document_id=%s",
                kb_id,
                document_id,
            )
            return None