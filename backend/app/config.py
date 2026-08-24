from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

class Settings(BaseSettings):
    app_name: str = "Elite Dev Events API"
    database_url: str = "postgresql+psycopg://elite:elite@db:5432/elite"
    jwt_secret: str = "change-me-in-production"
    jwt_exp_minutes: int = 60 * 12
    ticket_secret: str = "change-me-ticket-secret"
    frontend_url: str = "http://localhost:3000"
    tmdb_api_key: str | None = None
    ticketmaster_api_key: str | None = None
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_currency: str = "brl"
    stripe_checkout_expiration_minutes: int = 30
    stripe_test_mode: bool = True
    enable_simulated_payments: bool = False
    cors_origins: str = "http://localhost:3000"
    app_timezone: str = "America/Sao_Paulo"

    @field_validator("stripe_checkout_expiration_minutes")
    @classmethod
    def validate_stripe_checkout_expiration(cls, value: int) -> int:
        if not 30 <= value <= 1440:
            raise ValueError("must be between 30 minutes and 24 hours")
        return value

    @field_validator("stripe_currency")
    @classmethod
    def normalize_stripe_currency(cls, value: str) -> str:
        value = value.strip().lower()
        if len(value) != 3 or not value.isalpha():
            raise ValueError("must be a three-letter ISO currency code")
        return value

    @field_validator("app_timezone")
    @classmethod
    def validate_app_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("must be a valid IANA timezone") from exc
        return value

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return "postgresql+psycopg://" + value[len("postgres://"):]
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value[len("postgresql://"):]
        return value

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
