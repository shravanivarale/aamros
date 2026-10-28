from typing import Annotated, Optional, List, Dict, Any
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import require_roles
from app.core.enums import UserRole
from app.db.session import get_db
from app.models.user import User
from app.models.robot import Robot
from app.models.order import CustomerOrder
from app.models.shipment import IncomingShipment
from app.models.warehouse import Product

router = APIRouter(prefix="/admin", tags=["Admin Portal"])


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    phone: Optional[str] = None


class UserDetailResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    phone: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class AdminStatsResponse(BaseModel):
    total_users: int
    total_products: int
    total_orders: int
    total_shipments: int
    total_robots: int
    active_robots: int


@router.get("/users", response_model=List[UserDetailResponse])
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMINISTRATOR))],
):
    """List all platform users with role permissions."""
    result = await db.execute(select(User).where(User.deleted_at.is_(None)).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [
        UserDetailResponse(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            role=u.role,
            is_active=u.is_active,
            phone=u.phone,
            created_at=u.created_at.isoformat() if u.created_at else datetime.now(timezone.utc).isoformat(),
        )
        for u in users
    ]


@router.put("/users/{user_id}", response_model=UserDetailResponse)
async def update_user(
    user_id: str,
    data: UserUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMINISTRATOR))],
):
    """Update user role, active status, or details."""
    result = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if data.full_name is not None:
        target_user.full_name = data.full_name
    if data.role is not None:
        target_user.role = data.role
    if data.is_active is not None:
        target_user.is_active = data.is_active
    if data.phone is not None:
        target_user.phone = data.phone

    await db.commit()
    await db.refresh(target_user)

    return UserDetailResponse(
        id=target_user.id,
        email=target_user.email,
        full_name=target_user.full_name,
        role=target_user.role,
        is_active=target_user.is_active,
        phone=target_user.phone,
        created_at=target_user.created_at.isoformat() if target_user.created_at else datetime.now(timezone.utc).isoformat(),
    )


@router.delete("/users/{user_id}")
async def deactivate_user(
    user_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMINISTRATOR))],
):
    """Deactivate or soft-delete user account."""
    if current_admin.id == user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate your own account")

    result = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    target_user.is_active = False
    await db.commit()
    return {"status": "success", "message": f"User {target_user.email} deactivated"}


@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMINISTRATOR, UserRole.WAREHOUSE_OPERATOR))],
):
    """Aggregate dashboard metrics."""
    users_cnt = (await db.execute(select(func.count(User.id)).where(User.deleted_at.is_(None)))).scalar() or 0
    prods_cnt = (await db.execute(select(func.count(Product.id)))).scalar() or 0
    orders_cnt = (await db.execute(select(func.count(CustomerOrder.id)))).scalar() or 0
    ship_cnt = (await db.execute(select(func.count(IncomingShipment.id)))).scalar() or 0
    robots_res = await db.execute(select(Robot))
    robots = robots_res.scalars().all()

    active_cnt = sum(1 for r in robots if r.status in ["busy", "working", "moving", "picking"])

    return AdminStatsResponse(
        total_users=users_cnt,
        total_products=prods_cnt,
        total_orders=orders_cnt,
        total_shipments=ship_cnt,
        total_robots=len(robots),
        active_robots=active_cnt,
    )


@router.get("/settings")
async def get_system_settings(
    _: Annotated[User, Depends(require_roles(UserRole.ADMINISTRATOR, UserRole.WAREHOUSE_OPERATOR))],
):
    """Get active system runtime details."""
    settings = get_settings()
    is_supabase = "supabase" in settings.effective_database_url or "pooler" in settings.effective_database_url
    is_sqlite = "sqlite" in settings.effective_database_url

    return {
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "environment": settings.environment,
        "database_provider": "Supabase PostgreSQL" if is_supabase else ("SQLite Embedded" if is_sqlite else "PostgreSQL"),
        "supabase_configured": bool(settings.supabase_url or is_supabase),
        "firebase_auth_enabled": True,
        "api_v1_prefix": settings.api_v1_prefix,
    }
