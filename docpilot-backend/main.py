from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.core.config import get_settings
from app.db.init_db import init_db
from app.api.users import router as user_router
from app.core.exception_handlers import register_exception_handlers
from app.core.middleware import request_log_middleware
from fastapi.middleware.cors import CORSMiddleware
from app.api.kb import router as kb_router
from app.core.logger import setup_logging

setup_logging()

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


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


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "env": settings.app_env,
    }
