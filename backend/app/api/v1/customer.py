from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_roles
from app.core.enums import UserRole
from app.db.session import get_db
from app.models.user import User
from app.models.warehouse import ProductCategory
from app.schemas.product import OrderCreate, OrderResponse, ProductCreate, ProductResponse
from app.services.order_service import OrderService
from app.services.product_service import ProductService

router = APIRouter(tags=["Customer Portal"])


class CategoryResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("/products", response_model=list[ProductResponse])
async def list_products(db: Annotated[AsyncSession, Depends(get_db)]):
    service = ProductService(db)
    try:
        return await service.list_products()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Database error processing request")


@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    data: ProductCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMINISTRATOR))],
):
    service = ProductService(db)
    try:
        return await service.create_product(data)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Conflict / constraint violation")
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Database error processing request")


@router.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    data: OrderCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(UserRole.CUSTOMER, UserRole.ADMINISTRATOR))],
):
    service = OrderService(db)
    try:
        return await service.create_order(current_user.id, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Conflict / constraint violation")
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Database error processing request")


@router.get("/orders", response_model=list[OrderResponse])
async def list_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    service = OrderService(db)
    customer_id = None if current_user.role in {UserRole.ADMINISTRATOR.value, UserRole.WAREHOUSE_OPERATOR.value} else current_user.id
    try:
        return await service.list_orders(customer_id)
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Database error processing request")


@router.get("/categories", response_model=List[CategoryResponse])
async def list_categories(db: Annotated[AsyncSession, Depends(get_db)]):
    """List all product categories (public endpoint)."""
    try:
        result = await db.execute(select(ProductCategory).where(ProductCategory.deleted_at.is_(None)))
        categories = result.scalars().all()
        # Seed a default category if none exist
        if not categories:
            default_cat = ProductCategory(name="General", description="General products")
            db.add(default_cat)
            await db.commit()
            await db.refresh(default_cat)
            return [CategoryResponse(id=default_cat.id, name=default_cat.name, description=default_cat.description)]
        return [CategoryResponse(id=c.id, name=c.name, description=c.description) for c in categories]
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Database error processing request")
