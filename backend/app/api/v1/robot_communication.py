"""/robot-communication: the staff-facing window onto the ROS 2 robot bridges (one per robot PC, managed under /bridges).

Live robot data comes from robot_sync (polled from the bridges, persisted, streamed over the WebSocket); everything that
changes what a robot does goes through that robot's own bridge. If a robot PC is unreachable these endpoints say so (503) -
nothing is faked or reported as accepted when it was not.
"""
import json
import uuid
from typing import Annotated, Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_roles
from app.core.enums import UserRole
from app.core.security import decode_token
from app.db.session import get_db
from app.models.location import MapLocation
from app.models.robot import Robot
from app.models.task import RobotEvent, RobotTask
from app.models.user import User
from app.schemas.robot_communication import CanonicalEnvelope, TaskSubmitRequest
from app.services.bridge_client import BridgeClient, BridgeOffline, pool
from app.services.live_state import live
from app.services.task_sync import sync_task_status_with_db  # noqa: F401  (re-exported: older code imported it from here)

router = APIRouter(prefix="/robot-communication", tags=["ROS 2 Robot Communication Pipeline"])

Staff = Annotated[User, Depends(require_roles(UserRole.ADMINISTRATOR, UserRole.WAREHOUSE_OPERATOR))]


def _offline(exc: "Exception | str") -> HTTPException:
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                         detail=f"Robot bridge unreachable ({exc}). Is wms_bridge running, and is its address listed under Settings → Robot bridges?")


def _first_client() -> BridgeClient:
    online = pool.online()
    if not online:
        raise _offline("no robot bridge is online")
    return online[0][1]


def _client_for_robot(ref: Optional[str]) -> tuple[Optional[dict], BridgeClient]:
    """The robot (DB id or bridge id) and its bridge's client; with no robot given, the first online bridge."""
    if ref:
        robot = live.find_robot(ref)
        if robot is None:
            raise HTTPException(422, detail=f"Robot {ref} is not connected")
        try:
            return robot, pool.for_robot(robot)
        except BridgeOffline as exc:
            raise _offline(exc)
    return None, _first_client()


async def _clients_for_task(db: AsyncSession, task_id: str) -> list[BridgeClient]:
    """The bridge that runs this task (via its robot); if unknown, every online bridge."""
    t = (await db.execute(select(RobotTask).where(RobotTask.id == task_id))).scalar_one_or_none()
    robot = live.find_robot(t.robot_id) if t and t.robot_id else None
    if robot:
        try:
            return [pool.for_robot(robot)]
        except BridgeOffline:
            pass
    return [c for _, c in pool.online()]


async def _forward_task(db: AsyncSession, task_id: str, method: str, path: str) -> Any:
    clients = await _clients_for_task(db, task_id)
    if not clients:
        raise _offline("no robot bridge is online")
    last: Exception = BridgeOffline("no answer")
    for c in clients:
        try:
            return await c.request(method, path)
        except BridgeOffline as exc:
            last = exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404 and len(clients) > 1:
                last = exc
                continue
            raise HTTPException(exc.response.status_code, detail=exc.response.text[:300])
    raise _offline(last) if isinstance(last, BridgeOffline) else HTTPException(404, detail="Task not found on any robot bridge")


# ── tasks ────────────────────────────────────────────────────────────────────
@router.post("/tasks", status_code=status.HTTP_202_ACCEPTED)
async def submit_robot_task(req: TaskSubmitRequest, _: Staff, db: Annotated[AsyncSession, Depends(get_db)]):
    """Submit a task by location codes (taught on the map). The robot plans and drives it; the backend only describes it."""
    codes = {req.source_location_id, req.destination_location_id}
    known = {l.code: l for l in (await db.execute(select(MapLocation).where(MapLocation.code.in_(codes)))).scalars().all()}
    missing = sorted(c for c in codes if c not in known)
    if missing:
        raise HTTPException(422, detail=f"Unknown location(s) {missing}: teach them on the warehouse map first")
    robot, client = _client_for_robot(req.robot_id)
    if robot is None:   # no robot named: prefer a free, localized one; otherwise let the first bridge queue it
        robot = next((r for r in live.robots.values() if r.get("status") == "IDLE" and r.get("localized") and r.get("allow_motion")), None)
        if robot:
            client = pool.for_robot(robot)

    task_id = str(uuid.uuid4())

    def loc(c: str) -> dict:
        l = known[c]
        return {"location_id": l.code, "location_type": l.kind, "slot_id": l.rack_slot_id, "rack_id": l.rack_id, "x": l.x, "y": l.y, "yaw": l.yaw}

    env = CanonicalEnvelope(message_type="TASK_CREATE", task_id=task_id, robot_id=robot["robot_id"] if robot else None, priority=req.priority,
                            payload={"task_type": req.task_type, "order_id": req.order_id, "product_id": req.product_id, "quantity": req.quantity,
                                     "source_location": loc(req.source_location_id), "destination_location": loc(req.destination_location_id)})
    db.add(RobotTask(id=task_id, task_type=req.task_type, status="queued", priority=req.priority, robot_id=robot["db_id"] if robot else None,
                     reference_type="order" if req.order_id else "manual", reference_id=req.order_id,
                     payload=json.dumps(env.model_dump()), product_id=req.product_id))
    await db.commit()
    try:
        res = await client.post("/tasks", env.model_dump())
    except BridgeOffline as exc:
        await sync_task_status_with_db(db, task_id, "FAILED", error="robot bridge unreachable")
        raise _offline(exc)
    await sync_task_status_with_db(db, task_id, "ASSIGNED")
    return {"status": "submitted", "task_id": task_id, "message_id": env.message_id, "ros_bridge_response": res}


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str, _: Staff, db: Annotated[AsyncSession, Depends(get_db)]):
    db_task = (await db.execute(select(RobotTask).where(RobotTask.id == task_id))).scalar_one_or_none()
    ros = None
    for c in await _clients_for_task(db, task_id):
        try:
            ros = await c.get(f"/tasks/{task_id}")
            break
        except (BridgeOffline, httpx.HTTPStatusError):
            continue
    if not db_task and not ros:
        raise HTTPException(404, detail="Task not found")
    return {"task_id": task_id, "status": (ros or {}).get("status") or (db_task.status if db_task else "UNKNOWN"),
            "priority": db_task.priority if db_task else (ros or {}).get("priority", 10),
            "error": db_task.error_message if db_task else None, "ros_bridge_state": ros}


@router.post("/tasks/{task_id}/cancel")
async def cancel_robot_task(task_id: str, _: Staff, db: Annotated[AsyncSession, Depends(get_db)]):
    res = await _forward_task(db, task_id, "POST", f"/tasks/{task_id}/cancel")
    # a queued/unstarted task is cancelled right away; a running one is confirmed by the bridge's TASK_CANCELLED event
    if (res or {}).get("status") == "cancelled":
        await sync_task_status_with_db(db, task_id, "CANCELLED", error="cancelled by operator")
    return res


@router.post("/tasks/{task_id}/pause")
async def pause_robot_task(task_id: str, _: Staff, db: Annotated[AsyncSession, Depends(get_db)]):
    return await _forward_task(db, task_id, "POST", f"/tasks/{task_id}/pause")


@router.post("/tasks/{task_id}/resume")
async def resume_robot_task(task_id: str, _: Staff, db: Annotated[AsyncSession, Depends(get_db)]):
    return await _forward_task(db, task_id, "POST", f"/tasks/{task_id}/resume")


# ── robots / events / health ─────────────────────────────────────────────────
@router.get("/robots")
async def list_robots(_: Staff, db: Annotated[AsyncSession, Depends(get_db)]):
    if live.online and live.robots:
        return list(live.robots.values())
    bots = (await db.execute(select(Robot).where(Robot.deleted_at.is_(None)))).scalars().all()   # nothing online: last known state
    return [{"robot_id": b.serial_number, "db_id": b.id, "status": "OFFLINE", "battery": None if (b.battery_level or 0) < 0 else b.battery_level,
             "position": {"x": b.position_x, "y": b.position_y, "yaw": 0.0} if b.position_x is not None else None,
             "current_task_id": b.current_task_id, "last_seen": b.last_odom_at.isoformat() if b.last_odom_at else None,
             "localized": False} for b in bots]


@router.get("/robots/{robot_id}")
async def get_robot_state(robot_id: str, _: Staff):
    robot = live.find_robot(robot_id)
    if not robot:
        raise HTTPException(404, detail="Robot not found or offline")
    return robot


@router.get("/state")
async def live_state(_: Staff):
    """Everything the live dashboards need in one call (every bridge's link state, health, every robot)."""
    return live.snapshot()


@router.get("/events")
async def list_recent_events(_: Staff, db: Annotated[AsyncSession, Depends(get_db)], limit: int = Query(100, le=500)):
    rows = (await db.execute(select(RobotEvent).order_by(RobotEvent.created_at.desc()).limit(limit))).scalars().all()
    out = []
    for r in rows:
        try:
            p = json.loads(r.payload) if r.payload else {}
        except ValueError:
            p = {}
        mid = p.pop("message_id", None) or r.id
        for k in ("_seq", "_bridge", "_endpoint"):
            p.pop(k, None)
        out.append({"message_id": mid, "message_type": r.event_type, "timestamp": r.created_at.isoformat() if r.created_at else None,
                    "task_id": r.task_id, "robot_id": r.robot_id, "payload": p})
    return out


@router.get("/health")
async def check_communication_health(_: Staff):
    bridges = live.snapshot()["bridges"]
    if not live.online:
        err = next((b["error"] for b in bridges if b["error"]), "no robot bridge configured" if not bridges else None)
        return {"status": "offline", "ros_initialized": False, "active_robots": 0, "pending_tasks": 0, "started_at": None,
                "node_name": "wms_bridge", "bridge_url": bridges[0]["url"] if bridges else None, "error": err, "bridges": bridges}
    online = [e for e in live.endpoints.values() if e.online]
    return dict(online[0].health, bridge_url=online[0].url, error=None, bridges=bridges,
                active_robots=sum(e.health.get("active_robots", 0) for e in online),
                pending_tasks=sum(e.health.get("pending_tasks", 0) for e in online))


class InitialPose(BaseModel):
    x: float
    y: float
    yaw_deg: float = 0.0
    robot_id: Optional[str] = None


@router.post("/initial-pose")
async def set_initial_pose(p: InitialPose, _: Staff):
    """Tell a robot where it stands on the map (it will not execute tasks until localized)."""
    _, client = _client_for_robot(p.robot_id)
    try:
        return await client.post("/initial_pose", {"x": p.x, "y": p.y, "yaw_deg": p.yaw_deg})
    except BridgeOffline as exc:
        raise _offline(exc)


# ── camera ───────────────────────────────────────────────────────────────────
@router.get("/video_feed")
async def get_robot_video_feed(db: Annotated[AsyncSession, Depends(get_db)], token: Optional[str] = Query(None),
                               robot_id: Optional[str] = Query(None)):
    """MJPEG camera stream of a robot (default: first online bridge). <img> tags cannot send an Authorization header,
    so staff pass their access token as ?token=."""
    user = None
    if token:
        try:
            payload = decode_token(token)
            user = (await db.execute(select(User).where(User.id == payload.get("sub"), User.deleted_at.is_(None)))).scalar_one_or_none()
        except ValueError:
            user = None
    if not user or not user.is_active or user.role not in (UserRole.ADMINISTRATOR.value, UserRole.WAREHOUSE_OPERATOR.value):
        raise HTTPException(401, detail="Staff token required")
    _, client = _client_for_robot(robot_id)

    async def stream():
        async with httpx.AsyncClient(timeout=None, headers=client.headers) as c:
            try:
                async with c.stream("GET", f"{client.base_url}/video_feed") as r:
                    async for chunk in r.aiter_bytes():
                        yield chunk
            except Exception:                                   # noqa: BLE001
                return

    return StreamingResponse(stream(), media_type="multipart/x-mixed-replace; boundary=frame")
