from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolved relative to this file, not the current working directory — every
# command in this project runs from backend/ (cd backend && uvicorn ...), so
# a bare "env_file=".env"" here would look for backend/.env, which doesn't
# exist. The real .env lives at the project root, three levels up from
# backend/app/core/.
_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


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
    mock_provider_url: str = "http://127.0.0.1:9100"
    generation_mock_only: bool = False
    mock_fallback_provider_url: str | None = None
    generation_real_fallback_provider: str | None = None
    circuit_breaker_failure_threshold: int = 3
    circuit_breaker_recovery_timeout_seconds: float = 30.0

    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
