import json
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import OrderStatus, TaskStatus, TaskType
from app.models.inventory import InventoryItem
from app.models.order import CustomerOrder, OrderItem
from app.models.warehouse import Product
from app.models.task import RobotTask
from app.schemas.product import OrderCreate, OrderResponse


class OrderService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_order(self, customer_id: str, data: OrderCreate) -> OrderResponse:
        total = 0.0
        order_items: list[OrderItem] = []

        for item in data.items:
            product = await self._get_product(item.product_id)
            await self._reserve_inventory(item.product_id, item.quantity)
            order_items.append(
                OrderItem(
                    product_id=item.product_id,
                    quantity=item.quantity,
                    unit_price=product.unit_price,
                )
            )
            total += product.unit_price * item.quantity

        order = CustomerOrder(
            order_number=f"ORD-{uuid.uuid4().hex[:8].upper()}",
            customer_id=customer_id,
            status=OrderStatus.CONFIRMED.value,
            total_amount=total,
            notes=data.notes,
            items=order_items,
        )
        self.db.add(order)
        await self.db.flush()

        tasks = [
            RobotTask(
                task_type=TaskType.RETRIEVE_PRODUCT.value,
                status=TaskStatus.QUEUED.value,
                priority=3,
                reference_type="order",
                reference_id=order.id,
                product_id=item.product_id,
                payload=json.dumps({"order_number": order.order_number, "quantity": item.quantity}),
            )
            for item in order_items
        ]
        self.db.add_all(tasks)
        await self.db.flush()

        order.task_id = tasks[0].id if tasks else None
        order.status = OrderStatus.PROCESSING.value
        await self.db.flush()

        query = select(CustomerOrder).options(selectinload(CustomerOrder.items)).where(CustomerOrder.id == order.id)
        result = await self.db.execute(query)
        order_with_items = result.scalar_one()

        return OrderResponse.model_validate(order_with_items)

    async def list_orders(self, customer_id: Optional[str] = None) -> list[OrderResponse]:
        query = select(CustomerOrder).options(selectinload(CustomerOrder.items))
        if customer_id:
            query = query.where(CustomerOrder.customer_id == customer_id)
        query = query.order_by(CustomerOrder.created_at.desc())
        result = await self.db.execute(query)
        return [OrderResponse.model_validate(o) for o in result.scalars().all()]

    async def get_order(self, order_id: str) -> Optional[OrderResponse]:
        result = await self.db.execute(
            select(CustomerOrder)
            .options(selectinload(CustomerOrder.items))
            .where(CustomerOrder.id == order_id)
        )
        order = result.scalar_one_or_none()
        return OrderResponse.model_validate(order) if order else None

    async def _get_product(self, product_id: str) -> Product:
        result = await self.db.execute(select(Product).where(Product.id == product_id))
        product = result.scalar_one_or_none()
        if not product:
            raise ValueError(f"Product {product_id} not found")
        return product

    async def _reserve_inventory(self, product_id: str, quantity: int) -> None:
        result = await self.db.execute(
            select(InventoryItem).where(InventoryItem.product_id == product_id)
        )
        item = result.scalar_one_or_none()
        if not item or (item.quantity - item.reserved_quantity) < quantity:
            raise ValueError("Insufficient inventory")
        item.reserved_quantity += quantity
