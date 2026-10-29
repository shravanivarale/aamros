import json
import logging
from typing import Dict, Optional, Set

from fastapi import Query, WebSocket, WebSocketDisconnect

from app.core.enums import UserRole
from app.core.security import decode_token

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.robot_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info("WebSocket connected. Total: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)
        # Remove from robot connections if present
        for robot_id, ws in list(self.robot_connections.items()):
            if ws == websocket:
                del self.robot_connections[robot_id]
        logger.info("WebSocket disconnected. Total: %d", len(self.active_connections))

    async def broadcast(self, event_type: str, data: dict) -> None:
        message = json.dumps({"type": event_type, "data": data})
        dead: set[WebSocket] = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                dead.add(connection)
        
        for dead_conn in dead:
            self.disconnect(dead_conn)

    async def send_to_robot(self, robot_id: str, event_type: str, data: dict) -> bool:
        if robot_id in self.robot_connections:
            try:
                message = json.dumps({"type": event_type, "data": data})
                await self.robot_connections[robot_id].send_text(message)
                return True
            except Exception:
                self.disconnect(self.robot_connections[robot_id])
        return False


manager = ConnectionManager()


STAFF_ROLES = {UserRole.ADMINISTRATOR.value, UserRole.WAREHOUSE_OPERATOR.value}
ROBOT_COMMANDS = {"emergency_stop", "clear_estop", "manual_velocity", "cancel_task", "go_to", "dock"}


async def _role_of(token: Optional[str]) -> Optional[str]:
    """Role of the token's user (None = anonymous / invalid). Anonymous sockets receive broadcasts but cannot command the robot."""
    if not token:
        return None
    from sqlalchemy import select
    from app.db.session import AsyncSessionLocal
    from app.models.user import User
    try:
        sub = decode_token(token).get("sub")
        async with AsyncSessionLocal() as db:
            user = (await db.execute(select(User).where(User.id == sub, User.deleted_at.is_(None)))).scalar_one_or_none()
        return user.role if user and user.is_active else None
    except Exception:                                           # noqa: BLE001
        return None


async def _run_robot_command(websocket: WebSocket, command: str, payload: dict) -> None:
    from app.db.session import AsyncSessionLocal
    from app.services.bridge_client import BridgeOffline
    from app.services.robot_service import RobotService
    robot_id = payload.get("robot_id")
    body = {k: v for k, v in payload.items() if k != "robot_id"}
    try:
        async with AsyncSessionLocal() as db:
            await RobotService(db).send_command(robot_id, command, body)
    except (ValueError, BridgeOffline) as exc:
        await websocket.send_text(json.dumps({"type": "command_error", "data": {"command": command, "robot_id": robot_id, "error": str(exc)}}))


async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = Query(None)) -> None:
    if token:
        try:
            decode_token(token)
        except Exception as exc:
            logger.warning("WebSocket token validation failed: %s", exc)
            try:
                await websocket.accept()
                await websocket.close(code=1008, reason="Invalid or expired token")
            except Exception:
                pass
            return
    role = await _role_of(token)

    await manager.connect(websocket)
    try:
        from app.services.robot_sync import robot_sync
        for kind, data in await robot_sync.snapshot_messages():
            await websocket.send_text(json.dumps({"type": kind, "data": data}))
        while True:
            data_str = await websocket.receive_text()
            try:
                data = json.loads(data_str)
                msg_type = data.get("type")
                payload = data.get("data", {})

                logger.debug("WebSocket received: %s", msg_type)

                if msg_type == "register_robot":
                    robot_id = payload.get("robot_id")
                    if robot_id:
                        manager.robot_connections[robot_id] = websocket
                        logger.info("Registered robot %s for directed messaging", robot_id)
                elif msg_type == "robot_command":
                    msg_type, payload = payload.get("command"), payload.get("payload") or payload
                if msg_type in ROBOT_COMMANDS:
                    if role in STAFF_ROLES:
                        await _run_robot_command(websocket, msg_type, payload)
                    else:
                        await websocket.send_text(json.dumps({"type": "command_error", "data": {
                            "command": msg_type, "error": "Staff login required to command the robot"}}))
            except json.JSONDecodeError:
                logger.warning("Received invalid JSON on websocket: %s", data_str)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
