from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, HTTPException
from app.core.config import get_settings
from app.core.redis import redis_client
from app.core.storage import data_directories
from app.db.session import async_engine
from app.db.init_db import init_db
from app.api.users import router as user_router
from app.core.exception_handlers import register_exception_handlers
from app.core.middleware import request_log_middleware
from fastapi.middleware.cors import CORSMiddleware
from app.api.kb import router as kb_router
from app.api.chat import router as chat_router
from app.api.report import router as report_router
from app.core.logger import setup_logging
from redis.exceptions import RedisError
from sqlalchemy import text

setup_logging()

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    data_directories(settings)
    await init_db()
    try:
        await redis_client.ping()
        logger.info("Redis connectivity check succeeded")
    except RedisError:
        logger.warning("Redis connectivity check failed; authenticated requests will be unavailable")

    try:
        yield
    finally:
        await redis_client.aclose()
        await async_engine.dispose()


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(request_log_middleware)

register_exception_handlers(app)

# 路由挂载
router = app.include_router(user_router)
router = app.include_router(kb_router)
router = app.include_router(chat_router)
router = app.include_router(report_router)


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "env": settings.app_env,
    }


@app.get("/health/ready")
async def readiness_check():
    try:
        async with async_engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        await redis_client.ping()
    except Exception as exc:
        logger.warning("Readiness check failed: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Service dependencies are unavailable") from None

    return {"status": "ready"}
