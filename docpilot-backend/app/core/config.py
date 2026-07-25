from functools import lru_cache
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

    # Redis 配置
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str | None = None

    # 登录限流：每个 IP 每 60 秒最多 10 次
    login_rate_limit: int = 10
    login_rate_window_seconds: int = 60

    # 问答限流：每个用户每 60 秒最多 20 次
    chat_rate_limit: int = 20
    chat_rate_window_seconds: int = 60

    # 同一用户同时最多运行 2 个问答请求
    chat_concurrency_limit: int = 2

    # 并发租约最长保留 10 分钟
    chat_concurrency_lease_seconds: int = 600

    # 文档上传：每个用户每 60 秒最多 5 次
    upload_rate_limit: int = 5
    upload_rate_window_seconds: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()