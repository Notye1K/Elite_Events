from pydantic_settings import BaseSettings, SettingsConfigDict, field_validator

class Settings(BaseSettings):
    app_name: str = "Elite Dev Events API"
    database_url: str = "postgresql+psycopg://elite:elite@db:5432/elite"
    jwt_secret: str = "change-me-in-production"
    jwt_exp_minutes: int = 60 * 12
    ticket_secret: str = "change-me-ticket-secret"
    frontend_url: str = "http://localhost:3000"
    ticketmaster_api_key: str | None = None
    tmdb_api_key: str | None = None
    cors_origins: str = "http://localhost:3000"

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
