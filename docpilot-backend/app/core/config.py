from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "docpilot-backend"
    app_env: str = "dev"
    debug: bool = True

    openai_api_key: str
    openai_base_url: str
    model_name: str
    embedding_model: str

    database_url: str
    redis_url: str
    redis_token_ttl_seconds: int = 604800

    upload_dir: str = "/data/uploads"
    export_dir: str = "/data/exports"
    chroma_persist_dir: str = "/data/chroma"
    log_dir: str = "/data/logs"

    sql_echo: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_pool_recycle: int = 1800
    db_pool_pre_ping: bool = True

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )

    model_config = SettingsConfigDict(
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
