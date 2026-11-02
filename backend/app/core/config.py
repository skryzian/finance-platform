from functools import lru_cache
from typing import List

from pydantic import Field, field_validator, model_validator
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
    market_data_provider: str = "alpha_vantage"
    exchange_rate_provider: str = "frankfurter_ecb"
    alpha_vantage_api_key: str = ""
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
    sendgrid_api_key: str = ""
    sendgrid_from_email: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    expo_access_token: str = ""
    notification_max_attempts: int = Field(default=5, ge=1, le=20)
    mpesa_enabled: bool = False
    mpesa_environment: str = "sandbox"
    mpesa_consumer_key: str = ""
    mpesa_consumer_secret: str = ""
    mpesa_shortcode: str = ""
    mpesa_passkey: str = ""
    mpesa_transaction_type: str = "CustomerPayBillOnline"
    mpesa_callback_base_url: str = ""
    mpesa_callback_token: str = ""
    mpesa_live_payments_enabled: bool = False

    @field_validator("database_url", mode="before")
    @classmethod
    def use_psycopg_driver(cls, value: str) -> str:
        if value.startswith(("postgres://", "postgresql://")):
            return "postgresql+psycopg://" + value.split("://", 1)[1]
        return value

    @model_validator(mode="after")
    def require_production_secrets(self):
        if self.app_env.lower() in {"production", "prod"}:
            secrets = (self.jwt_secret, self.jwt_refresh_secret)
            if any(
                len(secret) < 32 or "change-me" in secret.lower() or "replace-" in secret.lower()
                for secret in secrets
            ):
                raise ValueError("Production requires separate, strong JWT secrets")
            if self.jwt_secret == self.jwt_refresh_secret:
                raise ValueError("JWT access and refresh secrets must be different")
        if self.mpesa_environment not in {"sandbox", "production"}:
            raise ValueError("MPESA_ENVIRONMENT must be sandbox or production")
        if self.mpesa_transaction_type not in {"CustomerPayBillOnline", "CustomerBuyGoodsOnline"}:
            raise ValueError("MPESA_TRANSACTION_TYPE must match a supported STK Push flow")
        if self.mpesa_enabled:
            required = (
                self.mpesa_consumer_key,
                self.mpesa_consumer_secret,
                self.mpesa_shortcode,
                self.mpesa_passkey,
                self.mpesa_callback_base_url,
                self.mpesa_callback_token,
            )
            if any(not value for value in required):
                raise ValueError("Enabled M-Pesa integration requires credentials and callback configuration")
            if len(self.mpesa_callback_token) < 32:
                raise ValueError("MPESA_CALLBACK_TOKEN must be at least 32 characters")
            if self.mpesa_environment == "production" and not self.mpesa_callback_base_url.startswith("https://"):
                raise ValueError("Production M-Pesa callbacks require an HTTPS base URL")
        if self.mpesa_live_payments_enabled and (
            self.mpesa_environment != "production" or not self.mpesa_enabled
        ):
            raise ValueError("Live M-Pesa payments require the enabled production integration")
        return self

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
