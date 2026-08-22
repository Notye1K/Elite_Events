from pydantic_settings import BaseSettings, SettingsConfigDict

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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
