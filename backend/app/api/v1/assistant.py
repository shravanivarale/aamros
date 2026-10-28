import json
import logging
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.inventory import InventoryItem
from app.models.order import CustomerOrder
from app.models.robot import Robot
from app.models.shipment import IncomingShipment
from app.models.user import User
from app.models.warehouse import Product

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/assistant", tags=["Assistant"])


class AssistantMessage(BaseModel):
    role: str
    content: str


class AssistantRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[AssistantMessage] = Field(default_factory=list, max_length=10)


class AssistantResponse(BaseModel):
    answer: str
    data: dict[str, Any] | None = None
    navigate_to: str | None = None


ALLOWED_ACTIONS = {
    "dashboard_summary", "list_orders", "list_products", "list_robots", "list_shipments", "navigate",
}
ALLOWED_ROUTES = {
    "/dashboard", "/orders", "/products", "/inventory", "/robots", "/robot-fleet",
    "/shipping", "/analytics", "/reports", "/slotting/recommendations",
}


async def classify_request(message: str, history: list[AssistantMessage]) -> dict[str, Any]:
    settings = get_settings()
    if not settings.groq_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The assistant is not configured yet. Add GROQ_API_KEY to backend/.env and restart the backend.",
        )

    conversation = "\n".join(f"{item.role}: {item.content}" for item in history[-6:])
    system_prompt = """You are the command router for an autonomous warehouse dashboard.
Return JSON only, with exactly these keys: action and route.
Allowed action values: dashboard_summary, list_orders, list_products, list_robots, list_shipments, navigate.
Use list_robots and list_shipments only when the user asks about robots or inbound shipments.
Use navigate when the user asks to open, go to, or show a dashboard section. For navigate, route must be one of:
/dashboard, /orders, /products, /inventory, /robots, /robot-fleet, /shipping, /analytics, /reports, /slotting/recommendations.
For all other requests, choose the closest read action. Never invent actions, routes, or data.
"""
    payload = {
        "model": settings.groq_model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Recent conversation:\n{conversation}\n\nCurrent request: {message}"},
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                json=payload,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            result = json.loads(content)
    except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
        logger.exception("Groq assistant request failed: %s", exc)
        raise HTTPException(status_code=502, detail="The assistant could not understand that request right now.") from exc

    action = result.get("action") if result.get("action") in ALLOWED_ACTIONS else "dashboard_summary"
    route = result.get("route") if result.get("route") in ALLOWED_ROUTES else None
    if action != "navigate":
        route = None
    return {"action": action, "route": route}


async def load_action_data(action: str, user: User, db: AsyncSession) -> dict[str, Any]:
    is_staff = user.role in {"administrator", "warehouse_operator"}
    if action == "list_orders":
        query = select(CustomerOrder).options(selectinload(CustomerOrder.items)).order_by(CustomerOrder.created_at.desc()).limit(10)
        if not is_staff:
            query = query.where(CustomerOrder.customer_id == user.id)
        orders = (await db.execute(query)).scalars().all()
        return {"orders": [{"order_number": item.order_number, "status": item.status, "total_amount": item.total_amount, "items": len(item.items)} for item in orders]}

    if action == "list_products":
        rows = (await db.execute(select(Product).order_by(Product.name).limit(20))).scalars().all()
        return {"products": [{"name": item.name, "sku": item.sku, "unit_price": item.unit_price} for item in rows]}

    if action == "list_robots" and not is_staff:
        return {"restricted": True}

    if action == "list_robots" and is_staff:
        rows = (await db.execute(select(Robot).where(Robot.deleted_at.is_(None)).order_by(Robot.name))).scalars().all()
        return {"robots": [{"name": item.name, "status": item.status, "battery_level": item.battery_level} for item in rows]}

    if action == "list_shipments" and not is_staff:
        return {"restricted": True}

    if action == "list_shipments" and is_staff:
        rows = (await db.execute(select(IncomingShipment).order_by(IncomingShipment.created_at.desc()).limit(10))).scalars().all()
        return {"shipments": [{"shipment_number": item.shipment_number, "status": item.status} for item in rows]}

    order_filter = CustomerOrder.customer_id == user.id if not is_staff else True
    order_count = await db.scalar(select(func.count()).select_from(CustomerOrder).where(order_filter))
    product_count = await db.scalar(select(func.count()).select_from(Product))
    summary: dict[str, Any] = {"orders": order_count or 0, "products": product_count or 0}
    if is_staff:
        summary["robots"] = await db.scalar(select(func.count()).select_from(Robot).where(Robot.deleted_at.is_(None))) or 0
        summary["shipments"] = await db.scalar(select(func.count()).select_from(IncomingShipment)) or 0
        summary["inventory_units"] = await db.scalar(select(func.coalesce(func.sum(InventoryItem.quantity - InventoryItem.reserved_quantity), 0)).select_from(InventoryItem)) or 0
    return summary


def build_answer(action: str, data: dict[str, Any], route: str | None, user: User) -> str:
    if action == "navigate" and route:
        return f"Opening {route.removeprefix('/').replace('-', ' ')} for you."
    if action == "list_orders":
        orders = data["orders"]
        return "You have no orders yet." if not orders else f"I found {len(orders)} recent order(s): " + ", ".join(f"{item['order_number']} ({item['status']})" for item in orders) + "."
    if action == "list_products":
        return f"There are {len(data['products'])} products in the catalog."
    if action == "list_robots":
        return "Fleet details are available to warehouse operators and administrators." if data.get("restricted") else f"I found {len(data['robots'])} robot(s) in the fleet."
    if action == "list_shipments":
        return "Inbound shipment details are available to warehouse operators and administrators." if data.get("restricted") else f"I found {len(data['shipments'])} recent inbound shipment(s)."
    return f"Here is your current view: {data['orders']} orders and {data['products']} products" + (f", {data['robots']} robots, and {data['shipments']} shipments." if user.role in {"administrator", "warehouse_operator"} else ".")


@router.post("/chat", response_model=AssistantResponse)
async def chat(
    request: AssistantRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    intent = await classify_request(request.message, request.history)
    action = intent["action"]
    data = {} if action == "navigate" else await load_action_data(action, user, db)
    return AssistantResponse(answer=build_answer(action, data, intent["route"], user), data=data or None, navigate_to=intent["route"])