from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "llm-gateway"
    environment: str = "development"
    postgres_db: str = "llm_gateway"
    postgres_user: str = "llm_gateway"
    postgres_password: str = "llm_gateway"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    redis_host: str = "localhost"
    redis_port: int = 6379
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    jwt_secret: str = "replace-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_ttl_minutes: int = 30
    jwt_refresh_token_ttl_days: int = 7
    cors_origins: List[str] = ["http://localhost:3000"]
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    mock_provider_url: str = "http://localhost:9100"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
