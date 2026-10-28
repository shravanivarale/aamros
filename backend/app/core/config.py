import os
import logging
from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_DEFAULT_DEV_URL = "postgresql+asyncpg://robu:robu_dev_password@localhost:5432/robu_warehouse"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "ARMS Fleet & Warehouse Platform"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"

    database_url: str = _DEFAULT_DEV_URL
    supabase_database_url: Optional[str] = None
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None
    firebase_project_id: Optional[str] = None
    redis_url: str = "redis://localhost:6379/0"

    secret_key: str = "robu-production-secure-jwt-secret-key-32-chars-long"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    refresh_token_expire_days: int = 14

    environment: str = "development"
    cors_origins: str = "http://localhost:5174,http://localhost:5173,http://localhost:3000,*"

    @property
    def effective_database_url(self) -> str:
        # Check explicit environment variables in priority order
        raw_url = (
            os.environ.get("SUPABASE_DATABASE_URL")
            or os.environ.get("DATABASE_URL")
            or os.environ.get("POSTGRES_URL")
            or self.supabase_database_url
            or self.database_url
        )

        # Normalize postgres driver for SQLAlchemy asyncpg
        if raw_url.startswith("postgres://"):
            raw_url = raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif raw_url.startswith("postgresql://") and not raw_url.startswith("postgresql+"):
            raw_url = raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)

        # Supabase URLs frequently include ?sslmode=require or &sslmode=require & ?pgbouncer=true
        # asyncpg does NOT support sslmode or pgbouncer as query params and will throw TypeError
        if "asyncpg" in raw_url and "?" in raw_url:
            base_part, query_part = raw_url.split("?", 1)
            # Remove asyncpg-incompatible params
            params = [
                p for p in query_part.split("&")
                if not p.startswith("sslmode=") and not p.startswith("pgbouncer=")
            ]
            raw_url = base_part + ("?" + "&".join(params) if params else "")

        # If it's a remote PostgreSQL (Supabase or cloud), return the asyncpg URL
        if not raw_url.endswith("robu_dev_password@localhost:5432/robu_warehouse"):
            return raw_url

        # Otherwise for local development or serverless fallback without Docker:
        # Resolve SQLite database path cleanly
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        db_path = os.path.join(base_dir, "robu_warehouse.db")
        # On Vercel serverless filesystem read-only root, use /tmp if needed
        if os.environ.get("VERCEL") and not os.path.exists(db_path):
            db_path = "/tmp/robu_warehouse.db"

        return f"sqlite+aiosqlite:///{db_path}"

    @property
    def cors_origins_list(self) -> List[str]:
        if "*" in self.cors_origins:
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()

