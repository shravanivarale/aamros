import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.middleware import ErrorLoggingMiddleware
from app.db.base import Base
import app.models  # noqa: F401
from sqlalchemy import text
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

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            try:
                await conn.execute(text("ALTER TABLE robots ADD COLUMN ip_address VARCHAR(50) DEFAULT '192.168.1.12'"))
            except Exception:
                pass
        logger.info("Database tables verified / created")

        # Auto-seed initial demo accounts and warehouse catalog if users table is empty
        try:
            from app.db.session import AsyncSessionLocal
            from app.models.user import User
            from app.models.warehouse import Product, ProductCategory, WarehouseZone
            from app.models.robot import Robot, RobotHealth
            from app.models.inventory import InventoryItem
            from app.core.security import get_password_hash
            from app.core.enums import UserRole
            from sqlalchemy import select

            async with AsyncSessionLocal() as db:
                user_check = await db.execute(select(User).limit(1))
                if not user_check.scalar_one_or_none():
                    logger.info("New database detected — auto-seeding demo users and catalog...")
                    users_to_seed = [
                        ("admin@arms.io", "admin12345", "ARMS System Administrator", UserRole.ADMINISTRATOR.value),
                        ("operator@arms.io", "operator123", "ARMS Fleet Operator", UserRole.WAREHOUSE_OPERATOR.value),
                        ("customer@arms.io", "customer123", "ARMS Demo Customer", UserRole.CUSTOMER.value),
                        ("admin@robu.io", "admin12345", "System Administrator", UserRole.ADMINISTRATOR.value),
                        ("operator@robu.io", "operator123", "Warehouse Operator", UserRole.WAREHOUSE_OPERATOR.value),
                        ("customer@robu.io", "customer123", "Demo Customer", UserRole.CUSTOMER.value),
                    ]
                    for email, pwd, name, role in users_to_seed:
                        db.add(User(
                            email=email,
                            hashed_password=get_password_hash(pwd),
                            full_name=name,
                            role=role,
                        ))
                    await db.commit()

                    cat = ProductCategory(name="Electronics", description="Electronic components and devices")
                    db.add(cat)
                    await db.flush()

                    products = [
                        Product(sku="SKU-001", name="Microcontroller Board", category_id=cat.id, unit_price=29.99),
                        Product(sku="SKU-002", name="Sensor Module Kit", category_id=cat.id, unit_price=49.99),
                        Product(sku="SKU-003", name="Motor Driver Unit", category_id=cat.id, unit_price=79.99),
                    ]
                    db.add_all(products)
                    await db.flush()

                    db.add_all([InventoryItem(product_id=p.id, quantity=100, reserved_quantity=0) for p in products])

                    robot = Robot(name="AMR-Alpha", serial_number="ROBU-001", status="idle", battery_level=95.0, ip_address="192.168.1.12")
                    db.add(robot)
                    await db.flush()
                    db.add(RobotHealth(robot_id=robot.id, connectivity="online"))

                    await db.commit()
                    logger.info("Demo catalog and accounts seeded successfully.")
        except Exception as seed_err:
            logger.debug("Auto-seed check: %s", seed_err)

    except Exception as exc:
        logger.warning("Could not auto-verify database on startup: %s", exc)

    yield

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
