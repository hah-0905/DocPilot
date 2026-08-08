from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.core.config import get_settings
from app.db.init_db import init_db
from app.api.users import router as user_router
from app.core.exception_handlers import register_exception_handlers
from app.core.middleware import request_log_middleware
from fastapi.middleware.cors import CORSMiddleware
from app.api.kb import router as kb_router
from app.api.chat import router as chat_router
from app.api.report import router as report_router
from app.api.settings import router as settings_router
from app.core.logger import setup_logging
from app.core.redis import check_redis_connection, close_redis, init_redis


setup_logging()

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_redis()

    try:
        yield
    finally:
        await close_redis()


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
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
router = app.include_router(settings_router)


@app.get("/health")
async def health_check():
    redis_available = await check_redis_connection()

    return {
        "status": "ok" if redis_available else "degraded",
        "app_name": settings.app_name,
        "env": settings.app_env,
        "redis": "ok" if redis_available else "unavailable",
    }