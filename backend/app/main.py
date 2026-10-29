import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.middleware import ErrorLoggingMiddleware
from app.db.bootstrap import init_schema, seed
import app.models  # noqa: F401
from app.db.session import engine
from app.websocket.gateway import websocket_endpoint

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # Configure logging first so every subsequent message is formatted
    configure_logging(
        level="DEBUG" if settings.is_development else "INFO",
        use_colour=True,
    )

    logger.info(
        "Starting %s v%s  [env=%s]",
        settings.app_name,
        settings.app_version,
        settings.environment,
    )

    serverless = bool(os.environ.get("VERCEL"))     # legacy Vercel function: stateless, no background loops
    if settings.is_production:
        problems = settings.check_production()
        if problems and serverless:
            # do not take a running site down; the Railway deployment enforces these strictly
            for msg in problems:
                logger.error("INSECURE CONFIGURATION (serverless, continuing): %s", msg)
        elif problems:
            for msg in problems:
                logger.error("Refusing to start: %s", msg)
            raise RuntimeError("Unsafe production configuration: " + " | ".join(problems))
    try:
        await init_schema()
        await seed(settings)
    except Exception as exc:
        if settings.is_production and not serverless:
            raise                                   # a production server without its database must fail its health check, not limp on
        logger.warning("Could not auto-verify database on startup: %s", exc)

    from app.services.robot_sync import robot_sync
    if not serverless:                              # the robot-sync loop needs a long-lived process (Railway), not a function
        await robot_sync.start()

    yield

    await robot_sync.stop()
    await engine.dispose()
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Autonomous Inventory Management Platform - Backend Orchestration Layer",
        lifespan=lifespan,
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
    )

    # ── Middleware (order matters: first added = outermost) ─────────────────
    app.add_middleware(ErrorLoggingMiddleware)          # catches all exceptions
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    app.websocket("/ws")(websocket_endpoint)

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "version": settings.app_version}

    return app


app = create_app()
