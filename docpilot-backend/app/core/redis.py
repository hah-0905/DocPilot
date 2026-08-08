import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings


logger = logging.getLogger(__name__)

_redis_client: Redis | None = None


async def init_redis() -> bool:
    """
    初始化 Redis 客户端。

    Redis 是任务状态缓存，不是主数据源。
    Redis 连接失败时记录日志，但不阻止 FastAPI 启动。
    """
    global _redis_client

    settings = get_settings()

    client = Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        password=settings.redis_password or None,
        protocol=2,
        decode_responses=True,
        socket_connect_timeout=3,
        socket_timeout=3,
        health_check_interval=30,
    )

    try:
        await client.ping()
    except RedisError:
        logger.exception(
            "Redis connection failed: host=%s, port=%s, db=%s",
            settings.redis_host,
            settings.redis_port,
            settings.redis_db,
        )

        await client.aclose()
        _redis_client = None
        return False

    _redis_client = client

    logger.info(
        "Redis connected: host=%s, port=%s, db=%s",
        settings.redis_host,
        settings.redis_port,
        settings.redis_db,
    )
    return True


def get_redis_client() -> Redis | None:
    """返回全局异步 Redis 客户端。"""
    return _redis_client


async def check_redis_connection() -> bool:
    """Check whether the initialized Redis client is still available."""
    client = get_redis_client()
    if client is None:
        return False

    try:
        return bool(await client.ping())
    except RedisError:
        logger.exception("Redis connection check failed")
        return False


async def close_redis() -> None:
    """关闭 Redis 客户端及连接池。"""
    global _redis_client

    if _redis_client is None:
        return

    try:
        await _redis_client.aclose()
        logger.info("Redis connection closed")
    finally:
        _redis_client = None