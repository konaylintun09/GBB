"""Application configuration, loaded from environment / .env."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Core
    database_url: str = "postgresql+asyncpg://flowea:flowea@db:5432/flowea_cmms"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 14

    # CORS — the front-end origins allowed to call this API
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # Seed demo data on first boot (set false in production)
    seed_demo: bool = True

    # One-time DB setup token for serverless hosts (used by POST /admin/init-db)
    setup_token: str | None = None

    # Object storage for photos/videos (optional; presign endpoint is disabled if unset)
    s3_endpoint_url: str | None = None      # e.g. https://<account>.r2.cloudflarestorage.com
    s3_region: str = "auto"
    s3_bucket: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def s3_enabled(self) -> bool:
        return all([self.s3_endpoint_url, self.s3_bucket, self.s3_access_key, self.s3_secret_key])


@lru_cache
def get_settings() -> Settings:
    return Settings()
