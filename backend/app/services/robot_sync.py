"""Real-time synchronisation with the ROS 2 robot bridges.

The admin manages the list of bridges (robot PCs) in the dashboard; every enabled one is polled independently and concurrently:
  every ros_sync_interval      robot telemetry -> live state + WebSocket `robot_position` / `robot_status` (+ DB, throttled to 1 Hz)
  every ros_event_interval     robot events    -> RobotEvent rows, task/order/shipment/stock sync (task_sync), WebSocket `robot_event`
  every ros_dispatch_interval  queued order/shipment tasks -> a free robot (task_dispatch), taught locations -> every bridge
  every 10 s                   the robot's active map -> WarehouseMap (what the dashboards draw)
An unreachable bridge marks only ITS robots offline (and is retried every few seconds); everything resumes by itself when it is back.
"""
import asyncio
import json
import logging
import math
import time
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlparse

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.bridge import BridgeEndpoint
from app.models.map import WarehouseMap
from app.models.robot import Robot, RobotHealth
from app.models.task import RobotEvent
from app.services.bridge_client import BridgeOffline, pool
from app.services.live_state import EndpointState, live
from app.services.map_service import MapService
from app.services.task_dispatch import dispatch_pending, push_locations
from app.services.task_sync import sync_task_status_with_db
from app.websocket.gateway import manager

logger = logging.getLogger(__name__)

STATUS_TO_DB = {"IDLE": "idle", "NAVIGATING": "navigating", "PAUSED": "busy", "OFFLINE": "offline",
                "EMERGENCY_STOP": "emergency_stop", "ERROR": "error"}
EVENT_TO_TASK_STATUS = {"TASK_STARTED": "STARTED", "NAVIGATING_TO_PICK": "STARTED", "NAVIGATING_TO_PLACE": "STARTED",
                        "ARRIVED_AT_PICK": "STARTED", "ARRIVED_AT_PLACE": "STARTED", "TASK_COMPLETED": "COMPLETED",
                        "TASK_FAILED": "FAILED", "TASK_CANCELLED": "CANCELLED"}
OFFLINE_RETRY_S = 3.0


class RobotSync:
    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._db_ids: dict[str, str] = {}              # "<endpoint>/<bridge robot id>" -> Robot.id
        self._last_db_write: dict[str, float] = {}
        self._last_status_key: dict[str, tuple] = {}
        self._last_status_sent: dict[str, float] = {}
        self._last_stale_check = 0.0

    # ── lifecycle ────────────────────────────────────────────────────────────
    async def start(self):
        if self._task is None and get_settings().ros_sync_enabled:
            await self._seed_first_endpoint()
            self._task = asyncio.create_task(self._loop(), name="robot-sync")
            logger.info("Robot sync started")

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._task = None
        await pool.close()

    async def _seed_first_endpoint(self):
        """A fresh install starts with the address from ROS_BRIDGE_URL; after that the dashboard owns the list."""
        async with AsyncSessionLocal() as db:
            if (await db.execute(select(BridgeEndpoint.id).limit(1))).first():
                return
            st = get_settings()
            u = urlparse(st.ros_bridge_url)
            if u.hostname:
                scheme = u.scheme if u.scheme in ("http", "https") else "http"
                db.add(BridgeEndpoint(name="Robot PC", host=u.hostname, port=u.port or (443 if scheme == "https" else 8005),
                                      scheme=scheme, token=st.ros_bridge_token, enabled=True))
                await db.commit()
                logger.info("Seeded bridge endpoint %s from ROS_BRIDGE_URL", st.ros_bridge_url)

    # ── loop ─────────────────────────────────────────────────────────────────
    async def _loop(self):
        s = get_settings()
        t_reload = t_dispatch = t_map = 0.0
        while True:
            t = time.monotonic()
            try:
                if t - t_reload >= 2.0 or not live.endpoints:
                    t_reload = t
                    await self._reload_endpoints()
                due = [ep for ep in live.endpoints.values() if t >= ep.next_poll]
                if due:
                    results = await asyncio.gather(*(self._poll_endpoint(ep, t) for ep in due), return_exceptions=True)
                    for r in results:
                        if isinstance(r, Exception) and not isinstance(r, asyncio.CancelledError):
                            logger.error("endpoint poll failed: %r", r)
                if live.online and t - t_dispatch >= s.ros_dispatch_interval:
                    t_dispatch = t
                    async with AsyncSessionLocal() as db:
                        await push_locations(db)
                        await dispatch_pending(db)
                if live.online and t - t_map >= 10.0:
                    t_map = t
                    await self._sync_map()
                await self._mark_unreported_offline(t)
            except asyncio.CancelledError:
                raise
            except Exception:                                   # noqa: BLE001
                logger.exception("robot sync iteration failed")
            await asyncio.sleep(s.ros_sync_interval)

    # ── endpoint list (managed from the dashboard) ───────────────────────────
    async def _reload_endpoints(self):
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(select(BridgeEndpoint).where(BridgeEndpoint.enabled == True))).scalars().all()  # noqa: E712
        wanted = {r.id: r for r in rows}
        for eid in [e for e in live.endpoints if e not in wanted]:
            await self._drop_endpoint(eid, "removed or disabled")
        for eid, r in wanted.items():
            ep = live.endpoints.get(eid)
            if ep is not None and (ep.url != r.url or ep.token != (r.token or None)):
                await self._drop_endpoint(eid, "address or token changed")
                ep = None
            if ep is None:
                live.endpoints[eid] = EndpointState(id=eid, name=r.name, url=r.url, token=r.token or None)
                logger.info("Watching robot bridge %s (%s)", r.name, r.url)
            else:
                ep.name = r.name

    async def _drop_endpoint(self, eid: str, why: str):
        ep = live.endpoints.get(eid)
        if ep:
            logger.info("Stopped watching robot bridge %s (%s): %s", ep.name, ep.url, why)
            await self._robots_offline(ep)
            live.endpoints.pop(eid, None)
        await pool.drop(eid)

    # ── one bridge ───────────────────────────────────────────────────────────
    async def _poll_endpoint(self, ep: EndpointState, now: float):
        s = get_settings()
        client = pool.client(ep)
        try:
            if now - ep.t_health >= 2.0 or not ep.health:
                ep.t_health = now
                await self._poll_health(ep, client)
            await self._poll_robots(ep, client)
            if now - ep.t_events >= s.ros_event_interval:
                ep.t_events = now
                await self._poll_events(ep, client)
            ep.next_poll = 0.0
        except BridgeOffline as exc:
            await self._go_offline(ep, str(exc))
            ep.next_poll = time.monotonic() + OFFLINE_RETRY_S
        except Exception as exc:                                # noqa: BLE001  (answers, but not like a wms_bridge)
            await self._go_offline(ep, f"unexpected answer: {exc}")
            ep.next_poll = time.monotonic() + OFFLINE_RETRY_S

    async def _poll_health(self, ep: EndpointState, client):
        h = await client.health()
        if ep.started_at and h.get("started_at") != ep.started_at:
            logger.info("Robot bridge %s restarted: resending locations, resetting the event cursor", ep.name)
            ep.locations_hash, ep.event_cursor = None, 0
        elif ep.started_at is None and not ep.cursor_loaded:
            ep.event_cursor = await self._stored_cursor(ep, h.get("started_at"))
            ep.cursor_loaded = True
        ep.started_at = h.get("started_at")
        ep.health = h

    async def _stored_cursor(self, ep: EndpointState, started_at: Optional[str]) -> int:
        """Resume after the last event already stored for THIS bridge run, so a backend restart does not replay history."""
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(select(RobotEvent).order_by(RobotEvent.created_at.desc()).limit(60))).scalars().all()
        for r in rows:
            try:
                p = json.loads(r.payload) if r.payload else {}
            except ValueError:
                continue
            if p.get("_endpoint") == ep.id:
                return int(p.get("_seq", 0)) if p.get("_bridge") == started_at else 0
        return 0

    # ── telemetry ────────────────────────────────────────────────────────────
    async def _poll_robots(self, ep: EndpointState, client):
        robots = await client.robots()
        was_online = ep.online
        ep.online, ep.last_error = True, None
        now = time.monotonic()
        async with AsyncSessionLocal() as db:
            for r in robots:
                rid = r["robot_id"]
                key = f"{ep.id}/{rid}"
                db_id = self._db_ids.get(key) or await self._ensure_robot(db, key, rid, ep)
                r["db_id"], r["endpoint_id"], r["endpoint_name"] = db_id, ep.id, ep.name
                live.robots[key] = r
                if r.get("position"):
                    await manager.broadcast("robot_position", self._position_msg(r, db_id))
                k = (r["status"], r.get("battery"), r.get("current_task_id"), r.get("localized"), r.get("estop"))
                changed = k != self._last_status_key.get(key)
                if changed or now - self._last_status_sent.get(key, 0) > 5.0:
                    self._last_status_key[key], self._last_status_sent[key] = k, now
                    await manager.broadcast("robot_status", self._status_msg(r, db_id))
                if changed or now - self._last_db_write.get(key, 0) >= 1.0:
                    self._last_db_write[key] = now
                    await self._write_robot(db, key, db_id, r)
            await db.commit()
        if not was_online:
            logger.info("Robot bridge %s online (%s)", ep.name, ep.url)

    @staticmethod
    def _position_msg(r: dict, db_id: str) -> dict[str, Any]:
        pos, vel = r["position"], r.get("velocity") or {}
        return {"robot_id": db_id, "bridge_robot_id": r["robot_id"], "x": pos["x"], "y": pos["y"], "yaw": pos["yaw"],
                "theta_z": math.sin(pos["yaw"] / 2), "theta_w": math.cos(pos["yaw"] / 2),
                "linear_velocity": vel.get("linear", 0.0), "angular_velocity": vel.get("angular", 0.0),
                "localized": r.get("localized"), "timestamp": datetime.now(timezone.utc).isoformat()}

    @staticmethod
    def _status_msg(r: dict, db_id: str) -> dict[str, Any]:
        bat = r.get("battery")
        return {"robot_id": db_id, "bridge_robot_id": r["robot_id"], "status": STATUS_TO_DB.get(r["status"], r["status"].lower()),
                "battery_level": bat if bat is not None else -1, "battery_known": bat is not None,
                "current_task_id": r.get("current_task_id"), "localized": r.get("localized"), "estop": r.get("estop"),
                "allow_motion": r.get("allow_motion"), "connectivity": (r.get("health") or {}).get("connectivity", "online"),
                "bridge": r.get("endpoint_name")}

    async def _ensure_robot(self, db, key: str, rid: str, ep: EndpointState) -> str:
        robot = (await db.execute(select(Robot).where((Robot.serial_number == rid) | (Robot.name == rid)).where(Robot.deleted_at.is_(None)))).scalars().first()
        host = urlparse(ep.url).hostname
        if robot is None:
            robot = Robot(name=rid, model="ArmsBot", serial_number=rid, ip_address=host, status="idle", battery_level=-1.0)
            db.add(robot)
            await db.flush()
            db.add(RobotHealth(robot_id=robot.id, connectivity="online"))
            await db.commit()
            logger.info("Registered robot %s from bridge %s", rid, ep.name)
        elif robot.ip_address != host:
            robot.ip_address = host                             # the robot lives where its bridge is
            await db.commit()
        self._db_ids[key] = robot.id
        return robot.id

    async def _write_robot(self, db, key: str, db_id: str, r: dict):
        robot = (await db.execute(select(Robot).where(Robot.id == db_id))).scalar_one_or_none()
        if robot is None:
            self._db_ids.pop(key, None)
            return
        pos, vel = r.get("position"), r.get("velocity") or {}
        robot.status = STATUS_TO_DB.get(r["status"], r["status"].lower())
        robot.battery_level = r["battery"] if r.get("battery") is not None else -1.0   # -1 = not measured (no battery sensor)
        robot.current_task_id = r.get("current_task_id")
        if pos:
            robot.position_x, robot.position_y = pos["x"], pos["y"]
            robot.orientation_z, robot.orientation_w = math.sin(pos["yaw"] / 2), math.cos(pos["yaw"] / 2)
        robot.linear_velocity, robot.angular_velocity = vel.get("linear"), vel.get("angular")
        robot.last_odom_at = datetime.now(timezone.utc)
        health = (await db.execute(select(RobotHealth).where(RobotHealth.robot_id == db_id))).scalar_one_or_none()
        if health is None:
            health = RobotHealth(robot_id=db_id)
            db.add(health)
        health.connectivity = (r.get("health") or {}).get("connectivity", "online")
        health.last_heartbeat = datetime.now(timezone.utc)

    async def _mark_unreported_offline(self, now: float):
        """Robots in the DB that no bridge reports (old rows, unplugged robots) are shown offline, never 'idle'."""
        if now - self._last_stale_check < 10.0:
            return
        self._last_stale_check = now
        reported = {r.get("db_id") for r in live.robots.values()}
        async with AsyncSessionLocal() as db:
            for stale in (await db.execute(select(Robot).where(Robot.deleted_at.is_(None), Robot.status != "offline"))).scalars().all():
                if stale.id not in reported:
                    stale.status, stale.battery_level, stale.current_task_id = "offline", -1.0, None
                    await manager.broadcast("robot_status", {"robot_id": stale.id, "status": "offline", "connectivity": "offline",
                                                             "battery_level": -1, "battery_known": False, "current_task_id": None})
            await db.commit()

    async def snapshot_messages(self) -> list[tuple[str, dict]]:
        """What a newly connected WebSocket client needs to draw the robots immediately (instead of waiting for the next change)."""
        out: list[tuple[str, dict]] = []
        for r in live.robots.values():
            if not r.get("db_id"):
                continue
            out.append(("robot_status", self._status_msg(r, r["db_id"])))
            if r.get("position"):
                out.append(("robot_position", self._position_msg(r, r["db_id"])))
        return out

    # ── offline handling (per bridge) ────────────────────────────────────────
    async def _go_offline(self, ep: EndpointState, why: str):
        first = ep.online or ep.last_error is None
        ep.online, ep.last_error, ep.health = False, why, {}
        if first:
            logger.warning("Robot bridge %s (%s) unreachable (%s): its robots are marked offline", ep.name, ep.url, why)
            await self._robots_offline(ep)

    async def _robots_offline(self, ep: EndpointState):
        keys = [k for k, r in live.robots.items() if r.get("endpoint_id") == ep.id]
        if not keys:
            return
        async with AsyncSessionLocal() as db:
            for key in keys:
                db_id = live.robots[key].get("db_id")
                robot = (await db.execute(select(Robot).where(Robot.id == db_id))).scalar_one_or_none() if db_id else None
                if robot:
                    robot.status = "offline"
                health = (await db.execute(select(RobotHealth).where(RobotHealth.robot_id == db_id))).scalar_one_or_none() if db_id else None
                if health:
                    health.connectivity = "offline"
                live.robots.pop(key, None)
                self._last_status_key.pop(key, None)
                await manager.broadcast("robot_status", {"robot_id": db_id, "bridge_robot_id": key.split("/", 1)[-1], "status": "offline",
                                                         "connectivity": "offline", "battery_level": -1, "battery_known": False,
                                                         "current_task_id": None, "localized": False})
            await db.commit()

    # ── events ───────────────────────────────────────────────────────────────
    async def _poll_events(self, ep: EndpointState, client):
        events = await client.events_since(ep.event_cursor)
        if not events:
            return
        async with AsyncSessionLocal() as db:
            for e in events:
                seq = int(e.get("seq", 0))
                if seq <= ep.event_cursor:
                    continue
                ep.event_cursor = seq
                rid = e.get("robot_id")
                db_id = self._db_ids.get(f"{ep.id}/{rid}") or (live.robots.get(f"{ep.id}/{rid}") or {}).get("db_id") or rid
                task_id, mtype = e.get("task_id"), e.get("message_type", "")
                payload = dict(e.get("payload") or {}, _seq=seq, _bridge=ep.started_at, _endpoint=ep.id, message_id=e.get("message_id"))
                db.add(RobotEvent(robot_id=db_id, task_id=task_id, event_type=mtype, payload=json.dumps(payload)))
                await db.commit()
                await manager.broadcast("robot_event", {"robot_id": db_id, "task_id": task_id, "message_type": mtype,
                                                        "timestamp": e.get("timestamp"), "payload": e.get("payload") or {}, "seq": seq,
                                                        "bridge": ep.name})
                if mtype == "TASK_FAILED" and db_id:
                    h = (await db.execute(select(RobotHealth).where(RobotHealth.robot_id == db_id))).scalar_one_or_none()
                    if h:
                        h.error_count += 1
                        await db.commit()
                if task_id and mtype in EVENT_TO_TASK_STATUS:
                    err = (e.get("payload") or {}).get("error_message") if mtype == "TASK_FAILED" else (
                        (e.get("payload") or {}).get("reason") if mtype == "TASK_CANCELLED" else None)
                    await sync_task_status_with_db(db, task_id, EVENT_TO_TASK_STATUS[mtype], error=err, robot_id=db_id)

    # ── map ──────────────────────────────────────────────────────────────────
    async def _sync_map(self):
        """The backend shows one warehouse map: the one the first online bridge localizes on."""
        for ep in live.endpoints.values():
            map_id = ep.health.get("map_id") if ep.online else None
            if not map_id:
                continue
            tag = f"bridge:{map_id}"
            async with AsyncSessionLocal() as db:
                cur = (await db.execute(select(WarehouseMap).where(WarehouseMap.is_active == True)  # noqa: E712
                                        .order_by(WarehouseMap.created_at.desc()))).scalars().first()
                if cur is not None and cur.pgm_path == tag:
                    return
                m = await pool.client(ep).get("/map")
                row = await MapService(db).upload_map(label=m["label"], pgm_data=m["pgm_data"], resolution=m["resolution"],
                                                      origin_x=m["origin_x"], origin_y=m["origin_y"],
                                                      width_px=m["width_px"], height_px=m["height_px"])
                row.pgm_path = tag
                await db.commit()
                logger.info("Active map synced from %s: %s (%dx%d, %.3f m/px)", ep.name, m["label"], m["width_px"], m["height_px"], m["resolution"])
            await manager.broadcast("map_update", {"map_id": row.id, "label": m["label"], "bridge_map_id": map_id})
            return


robot_sync = RobotSync()
