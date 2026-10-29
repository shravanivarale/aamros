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
    groq_api_key: Optional[str] = None
    groq_model: str = "openai/gpt-oss-20b"
    redis_url: str = "redis://localhost:6379/0"

    secret_key: str = "robu-production-secure-jwt-secret-key-32-chars-long"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    refresh_token_expire_days: int = 14

    # ROS 2 robot bridge (armsbot_nav wms_bridge) and the real-time sync with it
    ros_bridge_url: str = "http://10.113.140.148:8005"   # seeds the first bridge endpoint; more are managed in the dashboard
    ros_sync_enabled: bool = True
    ros_sync_interval: float = 0.5         # seconds between robot telemetry polls (position/status go to the WebSocket every poll)
    ros_event_interval: float = 1.0        # seconds between robot event polls
    ros_dispatch_interval: float = 2.0     # seconds between attempts to hand queued order/shipment tasks to the robot

    # First account and demo data. Production creates NO demo accounts; set ADMIN_EMAIL / ADMIN_PASSWORD for the first admin.
    seed_demo_data: Optional[bool] = None            # None = on in development, off otherwise
    admin_email: Optional[str] = None
    admin_password: Optional[str] = None
    admin_name: str = "Administrator"
    # Shared secret the backend sends to robot bridges that have an api_token (set the same value as the default for new bridges)
    ros_bridge_token: Optional[str] = None
    # auto | disable | require | verify-full. auto: no TLS on localhost and Railway's private network, 'require' (encrypted, certificate
    # not verified, like libpq sslmode=require) on Railway's public proxy, verified TLS for other remote databases (Supabase...)
    database_ssl: str = "auto"

    environment: str = "development"
    cors_origins: str = "http://localhost:5174,http://localhost:5173,http://localhost:3000"

    @property
    def effective_database_url(self) -> str:
        # DATABASE_URL is the canonical deployment setting. Keep the Supabase
        # names as fallbacks for existing local environments.
        raw_url = (
            os.environ.get("DATABASE_URL")
            or os.environ.get("SUPABASE_DATABASE_URL")
            or os.environ.get("POSTGRES_URL")
            or self.supabase_database_url
            or self.database_url
        )

        # A copied .env.example must not make local development wait on a fake remote database.
        if "YOUR_PROJECT_REF" in raw_url or "YOUR_DB_PASSWORD" in raw_url:
            raw_url = self.database_url

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

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def seed_demo(self) -> bool:
        return self.is_development if self.seed_demo_data is None else self.seed_demo_data

    def check_production(self) -> list[str]:
        """Things that must not reach a public deployment. Returns the problems (empty = fine)."""
        problems = []
        if self.secret_key.startswith("robu-production-secure-jwt-secret") or len(self.secret_key) < 32:
            problems.append("SECRET_KEY is the built-in default or shorter than 32 characters (anyone could forge logins). "
                            "Generate one: python -c \"import secrets; print(secrets.token_hex(32))\"")
        if self.effective_database_url.startswith("sqlite"):
            problems.append("DATABASE_URL is not set, so the app would use a local SQLite file that is erased on every deploy. "
                            "Add a PostgreSQL database and set DATABASE_URL.")
        if self.seed_demo:
            problems.append("SEED_DEMO_DATA is on: demo accounts with published passwords would be created.")
        if "*" in self.cors_origins_list:
            problems.append("CORS_ORIGINS contains '*': configure the exact Vercel origin before exposing the API publicly.")
        return problems


@lru_cache
def get_settings() -> Settings:
    return Settings()

