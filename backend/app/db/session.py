from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()
db_url = settings.effective_database_url

import os
from sqlalchemy.pool import NullPool

connect_args: dict[str, Any] = {}
extra_engine_kwargs: dict[str, Any] = {}

if "sqlite" in db_url:
    connect_args["check_same_thread"] = False
elif "asyncpg" in db_url:
    from urllib.parse import urlparse

    host = (urlparse(db_url.replace("postgresql+asyncpg://", "postgresql://", 1)).hostname or "")
    mode = settings.database_ssl.lower()
    if mode == "auto":
        if host in ("localhost", "127.0.0.1", "::1") or host.endswith(".railway.internal") or db_url.startswith("postgresql+asyncpg://robu:"):
            mode = "disable"
        elif host.endswith(".rlwy.net") or host.endswith(".railway.app"):
            mode = "require"                               # Railway public proxy: encrypted, certificate not verifiable
        else:
            mode = "verify-full"                           # Supabase etc.: asyncpg ssl=True == verify-full (the previous behaviour)
    if mode != "disable":
        connect_args["ssl"] = True if mode == "verify-full" else mode
    # Supabase Transaction Pooler (port 6543) requires statement caching disabled
    if "supabase" in db_url or "pooler" in db_url or ":6543" in db_url:
        connect_args["statement_cache_size"] = 0
        connect_args["prepared_statement_cache_size"] = 0
    # In serverless environments (e.g. Vercel) or when using Supabase pooler,
    # use NullPool to let Supavisor handle pooling without exhausting connections.
    if os.environ.get("VERCEL") or "pooler.supabase" in db_url or ":6543" in db_url:
        extra_engine_kwargs["poolclass"] = NullPool
    else:
        extra_engine_kwargs["pool_size"] = 5
        extra_engine_kwargs["max_overflow"] = 5

engine = create_async_engine(
    db_url,
    echo=False,
    pool_pre_ping=True,
    connect_args=connect_args,
    **extra_engine_kwargs,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

