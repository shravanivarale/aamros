"""Start-up database work: create tables, add missing columns, and (only when asked) create the first accounts.

Safe on SQLite and PostgreSQL. In production nothing is seeded unless ADMIN_EMAIL / ADMIN_PASSWORD are set, and demo accounts with
published passwords are never created (they are only for local development, SEED_DEMO_DATA).
"""
import logging

from sqlalchemy import inspect, select, text

from app.core.config import Settings
from app.core.enums import UserRole
from app.core.security import get_password_hash
from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine

logger = logging.getLogger(__name__)

# (table, column, DDL) added to databases created by an older version. create_all() never alters existing tables.
EXTRA_COLUMNS = [
    ("robots", "ip_address", "VARCHAR(50) DEFAULT '192.168.1.12'"),
    ("bridge_endpoints", "scheme", "VARCHAR(10) DEFAULT 'http' NOT NULL"),
    ("bridge_endpoints", "token", "VARCHAR(255)"),
]


def _ensure_columns(sync_conn) -> None:
    insp = inspect(sync_conn)
    tables = set(insp.get_table_names())
    for table, column, ddl in EXTRA_COLUMNS:
        if table in tables and column not in {c["name"] for c in insp.get_columns(table)}:
            sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
            logger.info("Added missing column %s.%s", table, column)


async def init_schema() -> None:
    # Two transactions on purpose: on PostgreSQL a failed statement aborts the whole transaction, which would roll the
    # table creation back with it.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with engine.begin() as conn:
        await conn.run_sync(_ensure_columns)
    logger.info("Database tables verified / created")


async def seed(settings: Settings) -> None:
    from app.models.inventory import InventoryItem
    from app.models.user import User
    from app.models.warehouse import Product, ProductCategory

    async with AsyncSessionLocal() as db:
        if (await db.execute(select(User.id).limit(1))).first():
            return
        if settings.seed_demo:
            logger.warning("Empty database: seeding DEMO accounts and catalog (SEED_DEMO_DATA). Never do this on a public server.")
            for email, pwd, name, role in [
                ("admin@arms.io", "admin12345", "ARMS System Administrator", UserRole.ADMINISTRATOR.value),
                ("operator@arms.io", "operator123", "ARMS Fleet Operator", UserRole.WAREHOUSE_OPERATOR.value),
                ("customer@arms.io", "customer123", "ARMS Demo Customer", UserRole.CUSTOMER.value),
                ("admin@robu.io", "admin12345", "System Administrator", UserRole.ADMINISTRATOR.value),
                ("operator@robu.io", "operator123", "Warehouse Operator", UserRole.WAREHOUSE_OPERATOR.value),
                ("customer@robu.io", "customer123", "Demo Customer", UserRole.CUSTOMER.value),
            ]:
                db.add(User(email=email, hashed_password=get_password_hash(pwd), full_name=name, role=role))
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
            await db.commit()
        elif settings.admin_email and settings.admin_password:
            db.add(User(email=settings.admin_email, hashed_password=get_password_hash(settings.admin_password),
                        full_name=settings.admin_name, role=UserRole.ADMINISTRATOR.value))
            await db.commit()
            logger.info("Created the first administrator account %s from ADMIN_EMAIL / ADMIN_PASSWORD", settings.admin_email)
        else:
            logger.warning("No users exist and ADMIN_EMAIL / ADMIN_PASSWORD are not set: nobody can log in until one admin is created")
