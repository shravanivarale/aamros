"""Hands queued order / shipment tasks to the robot and keeps the robot's location registry in step with the database.

The backend never drives the robot: it resolves WHERE (taught map locations) and sends a high-level TASK_CREATE envelope;
the bridge plans and drives. A task whose locations are not taught yet simply waits (with the reason visible on the task)
and is retried every cycle, so it starts by itself as soon as the missing location exists.
"""
import hashlib
import json
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import TaskType
from app.models.inventory import InventoryItem
from app.models.location import MapLocation
from app.models.slotting import SlotAssignment
from app.models.task import RobotTask
from app.models.warehouse import Shelf
from app.schemas.robot_communication import CanonicalEnvelope
from app.services.bridge_client import BridgeOffline, pool
from app.services.live_state import live
from app.websocket.gateway import manager

logger = logging.getLogger(__name__)
ACTIVE = ("assigned", "in_progress")


def _loc(l: MapLocation) -> dict:
    return {"location_id": l.code, "location_type": l.kind, "slot_id": l.rack_slot_id, "rack_id": l.rack_id,
            "x": l.x, "y": l.y, "yaw": l.yaw}


async def registry(db: AsyncSession) -> dict[str, dict]:
    rows = (await db.execute(select(MapLocation).order_by(MapLocation.code))).scalars().all()
    return {l.code: {"x": l.x, "y": l.y, "yaw": l.yaw, "type": l.kind} for l in rows}


async def push_locations(db: AsyncSession, force: bool = False) -> bool:
    """Send the whole registry to every online bridge whose copy is stale (changed registry or restarted bridge)."""
    reg = await registry(db)
    h = hashlib.sha1(json.dumps(reg, sort_keys=True).encode()).hexdigest()
    ok = True
    for ep, client in pool.online():
        if not force and h == ep.locations_hash:
            continue
        try:
            res = await client.post("/locations", reg)
        except BridgeOffline:
            ok = False
            continue
        ep.location_issues = (res or {}).get("rejected", {})
        for code, why in ep.location_issues.items():
            logger.warning("Robot bridge %s rejected location %s: %s", ep.name, code, why)
        ep.locations_hash = h
        logger.info("Pushed %d map locations to robot bridge %s", len(reg), ep.name)
    return ok


async def _first(db: AsyncSession, kind: str) -> Optional[MapLocation]:
    return (await db.execute(select(MapLocation).where(MapLocation.kind == kind).order_by(MapLocation.code))).scalars().first()


async def pick_location(db: AsyncSession, product_id: Optional[str]) -> Optional[MapLocation]:
    """Where is this product stored? slotting assignment first, then the rack of the shelf its stock sits on."""
    if not product_id:
        return None
    slot_ids = [a.slot_id for a in (await db.execute(select(SlotAssignment).where(SlotAssignment.product_id == product_id))).scalars().all()]
    if slot_ids:
        l = (await db.execute(select(MapLocation).where(MapLocation.rack_slot_id.in_(slot_ids)).order_by(MapLocation.code))).scalars().first()
        if l:
            return l
    inv = (await db.execute(select(InventoryItem).where(InventoryItem.product_id == product_id, InventoryItem.shelf_id.is_not(None)))).scalars().first()
    if inv:
        shelf = (await db.execute(select(Shelf).where(Shelf.id == inv.shelf_id))).scalar_one_or_none()
        if shelf:
            return (await db.execute(select(MapLocation).where(MapLocation.rack_id == shelf.rack_id).order_by(MapLocation.code))).scalars().first()
    return None


async def store_location(db: AsyncSession, product_id: Optional[str]) -> Optional[MapLocation]:
    """Where should an incoming crate go? the product's assigned slot, else the rack_slot location with the fewest queued tasks."""
    l = await pick_location(db, product_id)
    if l:
        return l
    slots = list((await db.execute(select(MapLocation).where(MapLocation.kind == "rack_slot").order_by(MapLocation.code))).scalars().all())
    if not slots:
        return None
    busy: dict[str, int] = {}
    for t in (await db.execute(select(RobotTask).where(RobotTask.reference_type == "shipment", RobotTask.status.in_(("queued", "assigned", "in_progress"))))).scalars().all():
        try:
            code = json.loads(t.payload or "{}").get("payload", {}).get("destination_location", {}).get("location_id")
        except ValueError:
            code = None
        busy[code] = busy.get(code, 0) + 1
    return min(slots, key=lambda s: (busy.get(s.code, 0), s.code))


async def build_envelope(db: AsyncSession, task: RobotTask, robot_id: str) -> tuple[Optional[CanonicalEnvelope], Optional[str]]:
    """-> (envelope, None) or (None, why it has to wait)."""
    meta = {}
    try:
        meta = json.loads(task.payload or "{}")
    except ValueError:
        pass
    if task.task_type == TaskType.RETRIEVE_PRODUCT.value:
        src, dst = await pick_location(db, task.product_id), await _first(db, "shipping")
        if not src:
            return None, "waiting: no taught map location for where this product is stored (teach a rack_slot location on the map)"
        if not dst:
            return None, "waiting: no 'shipping' location taught on the map"
    elif task.task_type == TaskType.STORE_CRATE.value:
        src, dst = await _first(db, "receiving"), await store_location(db, task.product_id)
        if not src:
            return None, "waiting: no 'receiving' location taught on the map"
        if not dst:
            return None, "waiting: no 'rack_slot' location taught on the map to store the crate"
    elif task.task_type == TaskType.RETURN_TO_DOCK.value:
        src, dst = None, await _first(db, "home")
        if not dst:
            return None, "waiting: no 'home' location taught on the map"
    else:
        return None, f"waiting: task type {task.task_type} is not executable by the robot"
    payload = {
        "task_type": "PICK_AND_PLACE" if src else "RETURN_TO_DOCK",
        "order_id": task.reference_id if task.reference_type == "order" else None,
        "product_id": task.product_id, "quantity": meta.get("quantity", 1),
        "source_location": _loc(src) if src else _loc(dst),
        "destination_location": _loc(dst),
        "metadata": {"reference_type": task.reference_type, "reference_id": task.reference_id},
    }
    return CanonicalEnvelope(message_type="TASK_CREATE", task_id=task.id, robot_id=robot_id, priority=task.priority, payload=payload), None


async def dispatch_pending(db: AsyncSession) -> int:
    """One pass: give the next waiting task to each free robot. Returns how many were handed over."""
    if not live.online:
        return 0
    robots = list(live.robots.values())
    if robots and not any(r.get("allow_motion") for r in robots):
        # tell the operator why nothing moves (once), instead of silently queueing forever
        why = "waiting: the robot bridge has motion disabled (start it with allow_motion:=true)"
    else:
        why = None
    free = [r for r in robots if r.get("db_id") and r.get("status") == "IDLE" and not r.get("estop") and r.get("localized") and r.get("allow_motion")]
    waiting = list((await db.execute(
        select(RobotTask).where(RobotTask.status == "queued", RobotTask.reference_type.in_(("order", "shipment")))
        .order_by(RobotTask.priority, RobotTask.created_at))).scalars().all())
    busy_robots = {t.robot_id for t in (await db.execute(select(RobotTask).where(RobotTask.status.in_(ACTIVE)))).scalars().all() if t.robot_id}
    handed = 0
    for task in waiting:
        reason = why
        robot = next((r for r in free if r["db_id"] not in busy_robots), None)
        if reason is None and robot is None:
            idle_unlocalized = [r for r in robots if r.get("status") == "IDLE" and not r.get("localized")]
            reason = "waiting: robot is not localized on the map (set its initial pose)" if idle_unlocalized else "waiting: no free robot"
        env = None
        if reason is None:
            env, reason = await build_envelope(db, task, robot["robot_id"])
        if reason is not None:
            if task.error_message != reason:
                task.error_message = reason
                await db.commit()
                await manager.broadcast("task_update", {"task_id": task.id, "status": task.status, "error": reason,
                                                       "reference_type": task.reference_type, "reference_id": task.reference_id})
            continue
        try:
            await pool.for_robot(robot).post("/tasks", env.model_dump())
        except Exception as exc:                                # noqa: BLE001
            logger.warning("Dispatch of task %s failed: %s", task.id, exc)
            continue
        task.status, task.robot_id, task.error_message = "assigned", robot["db_id"], None
        task.payload = json.dumps(env.model_dump())
        busy_robots.add(robot["db_id"])
        await db.commit()
        handed += 1
        logger.info("Task %s (%s) dispatched to %s", task.id, task.task_type, robot["robot_id"])
        await manager.broadcast("task_update", {"task_id": task.id, "status": "assigned", "robot_id": robot["db_id"],
                                                "reference_type": task.reference_type, "reference_id": task.reference_id})
    return handed
