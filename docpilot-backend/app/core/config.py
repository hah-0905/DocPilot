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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()