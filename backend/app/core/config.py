from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Finance Platform"
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/finance_db"
    jwt_secret: str = "change-me"
    jwt_refresh_secret: str = "change-me-refresh"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: List[str] = ["http://localhost:3000"]
    storage_provider: str = "s3"
    storage_bucket: str = "finance-platform-dev"
    storage_access_key: str = ""
    storage_secret_key: str = ""
    default_currency: str = "KES"
    default_country: str = "KE"
    market_data_provider: str = "unconfigured"
    exchange_rate_provider: str = "unconfigured"
    news_provider: str = "unconfigured"
    ai_provider: str = "openai"
    openai_api_key: str = ""
    openai_model: str = ""
    openai_enabled: bool = False
    ai_max_requests_per_user: int = Field(default=20, ge=1, le=10000)
    ai_global_max_requests_per_day: int = Field(default=1000, ge=1, le=1000000)
    ai_max_response_tokens: int = Field(default=600, ge=16, le=16384)
    ai_temperature: float | None = Field(default=None, ge=0, le=2)
    ai_request_timeout_seconds: float = Field(default=25.0, ge=1, le=120)
    ai_max_prompt_characters: int = Field(default=4000, ge=32, le=20000)
    ai_history_enabled_by_default: bool = False
    ai_history_retention_days: int = Field(default=30, ge=1, le=3650)
    ai_request_logging: bool = False
    ai_privacy_mode: bool = True

    @field_validator("database_url", mode="before")
    @classmethod
    def use_psycopg_driver(cls, value: str) -> str:
        if value.startswith(("postgres://", "postgresql://")):
            return "postgresql+psycopg://" + value.split("://", 1)[1]
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
