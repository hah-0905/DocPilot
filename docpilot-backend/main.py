from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.core.config import get_settings
from app.db.init_db import init_db
from app.api.users import router as user_router

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

# 路由挂载
router = app.include_router(user_router)


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "env": settings.app_env,
    }
