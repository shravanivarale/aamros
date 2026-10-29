"""Task lifecycle synchronisation: a robot task changing state updates its order / shipment, the stock and the audit trail.

Every stock change writes an InventoryEvent (who/which task/how much), is applied once per task, and is broadcast over the WebSocket.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import OrderStatus, ShipmentStatus
from app.models.inventory import InventoryEvent, InventoryItem
from app.models.order import CustomerOrder, OrderItem
from app.models.shipment import IncomingShipment, ShipmentItem
from app.models.task import RobotTask, TaskExecutionHistory
from app.websocket.gateway import manager

logger = logging.getLogger(__name__)

STATUS_MAP = {
    "PENDING": "pending", "QUEUED": "queued", "ASSIGNED": "assigned",
    "STARTED": "in_progress", "NAVIGATING": "in_progress", "PICKING": "in_progress", "PLACING": "in_progress",
    "PAUSED": "in_progress", "IN_PROGRESS": "in_progress",
    "COMPLETED": "completed", "FINISHED": "completed", "DELIVERED": "completed",
    "FAILED": "failed", "CANCELLED": "cancelled",
}
TERMINAL = {"completed", "failed", "cancelled"}


def normalize_status(raw: str) -> Optional[str]:
    return STATUS_MAP.get((raw or "").upper().replace("TASK_", ""))


async def _inventory_row(db: AsyncSession, product_id: str) -> Optional[InventoryItem]:
    res = await db.execute(select(InventoryItem).where(InventoryItem.product_id == product_id).order_by(InventoryItem.created_at))
    return res.scalars().first()


async def _siblings(db: AsyncSession, task: RobotTask) -> list[RobotTask]:
    res = await db.execute(select(RobotTask).where(RobotTask.reference_type == task.reference_type,
                                                   RobotTask.reference_id == task.reference_id))
    return list(res.scalars().all())


async def sync_task_status_with_db(db: AsyncSession, task_id: str, new_status: str,
                                   error: Optional[str] = None, robot_id: Optional[str] = None) -> Optional[RobotTask]:
    if not task_id or not new_status:
        return None
    target = normalize_status(new_status)
    if target is None:
        return None
    task = (await db.execute(select(RobotTask).where(RobotTask.id == task_id))).scalar_one_or_none()
    if task is None:
        return None
    current = (task.status or "").lower()
    if current in TERMINAL and current != target:
        return task                              # a finished task is never reopened and its stock effect is never applied twice
    if current == target:
        return task

    task.status = target
    if robot_id and not task.robot_id:
        task.robot_id = robot_id
    now = datetime.now(timezone.utc).isoformat()
    if target == "in_progress" and not task.started_at:
        task.started_at = now
    if target == "completed":
        task.completed_at = now
    if target in ("failed", "cancelled") and error:
        task.error_message = error
    db.add(TaskExecutionHistory(task_id=task.id, event_type=new_status.upper(), message=error, robot_id=task.robot_id))

    broadcasts: list[tuple[str, dict]] = []
    if task.reference_type == "order" and task.reference_id:
        broadcasts += await _sync_order(db, task, target)
    elif task.reference_type == "shipment" and task.reference_id:
        broadcasts += await _sync_shipment(db, task, target)

    await db.commit()
    await manager.broadcast("task_update", {"task_id": task.id, "status": target, "reference_type": task.reference_type,
                                            "reference_id": task.reference_id, "robot_id": task.robot_id, "error": task.error_message})
    for kind, data in broadcasts:
        await manager.broadcast(kind, data)
    return task


async def _sync_order(db: AsyncSession, task: RobotTask, target: str) -> list[tuple[str, dict]]:
    order = (await db.execute(select(CustomerOrder).where(CustomerOrder.id == task.reference_id))).scalar_one_or_none()
    if not order:
        return []
    items = list((await db.execute(select(OrderItem).where(OrderItem.order_id == order.id))).scalars().all())
    mine = [i for i in items if task.product_id is None or i.product_id == task.product_id]
    out: list[tuple[str, dict]] = []

    if target == "in_progress":
        if order.status in (OrderStatus.PENDING.value, OrderStatus.CONFIRMED.value, OrderStatus.PROCESSING.value):
            order.status = OrderStatus.RETRIEVING.value
        order.assigned_robot_id = task.robot_id or order.assigned_robot_id
    elif target == "completed":
        for it in mine:
            inv = await _inventory_row(db, it.product_id)
            if inv:
                inv.quantity = max(0, inv.quantity - it.quantity)
                inv.reserved_quantity = max(0, inv.reserved_quantity - it.quantity)
                db.add(InventoryEvent(product_id=it.product_id, inventory_item_id=inv.id, event_type="order_pick",
                                      quantity_change=-it.quantity, robot_id=task.robot_id, task_id=task.id,
                                      notes=f"order {order.order_number}"))
        out.append(("inventory_update", {"reason": "order_fulfillment", "order_id": order.id}))
    elif target == "cancelled":
        for it in mine:
            inv = await _inventory_row(db, it.product_id)
            if inv:
                inv.reserved_quantity = max(0, inv.reserved_quantity - it.quantity)
        out.append(("inventory_update", {"reason": "order_cancelled", "order_id": order.id}))

    if target in TERMINAL:
        sibs = await _siblings(db, task)
        states = [(t.status or "").lower() if t.id != task.id else target for t in sibs]
        if all(s in TERMINAL for s in states):
            if all(s == "completed" for s in states):
                order.status = OrderStatus.DELIVERED.value
            elif all(s == "cancelled" for s in states):
                order.status = OrderStatus.CANCELLED.value
    out.append(("order_update", {"order_id": order.id, "status": order.status, "task_id": task.id}))
    return out


async def _sync_shipment(db: AsyncSession, task: RobotTask, target: str) -> list[tuple[str, dict]]:
    shipment = (await db.execute(select(IncomingShipment).where(IncomingShipment.id == task.reference_id))).scalar_one_or_none()
    if not shipment:
        return []
    items = list((await db.execute(select(ShipmentItem).where(ShipmentItem.shipment_id == shipment.id))).scalars().all())
    mine = [i for i in items if i.product_id and (task.product_id is None or i.product_id == task.product_id)]
    out: list[tuple[str, dict]] = []

    if target == "in_progress":
        shipment.status = ShipmentStatus.STORING.value
        shipment.assigned_robot_id = task.robot_id or shipment.assigned_robot_id
    elif target == "completed":
        for it in mine:
            inv = await _inventory_row(db, it.product_id)
            if inv:
                inv.quantity += it.expected_quantity
            else:
                inv = InventoryItem(product_id=it.product_id, quantity=it.expected_quantity, reserved_quantity=0,
                                    aruco_marker_id=it.aruco_marker_id)
                db.add(inv)
                await db.flush()
            inv.last_verified_by_robot_id = task.robot_id
            inv.last_verified_at = datetime.now(timezone.utc).isoformat()
            it.status = "stored"
            db.add(InventoryEvent(product_id=it.product_id, inventory_item_id=inv.id, event_type="shipment_store",
                                  quantity_change=it.expected_quantity, robot_id=task.robot_id, task_id=task.id,
                                  notes=f"shipment {shipment.shipment_number}"))
        out.append(("inventory_update", {"reason": "shipment_intake", "shipment_id": shipment.id}))

    if target in TERMINAL:
        sibs = await _siblings(db, task)
        states = [(t.status or "").lower() if t.id != task.id else target for t in sibs]
        if all(s in TERMINAL for s in states):
            shipment.status = ShipmentStatus.COMPLETED.value if all(s == "completed" for s in states) else ShipmentStatus.FAILED.value
    out.append(("shipment_update", {"shipment_id": shipment.id, "status": shipment.status, "task_id": task.id}))
    return out
