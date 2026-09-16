"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "ControlFlow"
    environment: str = "development"

    database_url: str = "postgresql+psycopg://controlflow:controlflow@localhost:5432/controlflow"
    redis_url: str = "redis://localhost:6379/0"

    secret_key: str = "change-me-in-production-this-is-a-demo-secret-key"
    access_token_expire_minutes: int = 60 * 8
    jwt_algorithm: str = "HS256"

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    demo_seed: int = 20240101

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
