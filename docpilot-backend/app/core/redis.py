import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()


redis_client = Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    db=settings.redis_db,
    password=settings.redis_password,
    decode_responses=True,
    socket_connect_timeout=3,
    socket_timeout=3,
    health_check_interval=30,
)


async def check_redis_connection() -> bool:
    """
    检查 Redis 是否可以正常连接。
    """
    try:
        return bool(await redis_client.ping())
    except RedisError:
        logger.exception("Redis connection check failed")
        return False


async def close_redis_connection() -> None:
    """
    关闭 Redis 客户端和连接池。
    """
    await redis_client.aclose()