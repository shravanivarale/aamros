import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import RobotStatus
from app.models.robot import Robot, RobotHealth
from app.schemas.robot import RobotCreate, RobotResponse, RobotHealthResponse, RobotUpdate
from app.websocket.gateway import manager

logger = logging.getLogger(__name__)


class RobotService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_robots(self) -> list[RobotResponse]:
        result = await self.db.execute(
            select(Robot)
            .options(selectinload(Robot.health))
            .where(Robot.deleted_at.is_(None))
            .order_by(Robot.name)
        )
        return [RobotResponse.model_validate(r) for r in result.scalars().all()]

    async def get_robot(self, robot_id: str) -> Optional[RobotResponse]:
        result = await self.db.execute(select(Robot).where(Robot.id == robot_id))
        robot = result.scalar_one_or_none()
        return RobotResponse.model_validate(robot) if robot else None

    async def create_robot(self, data: RobotCreate) -> RobotResponse:
        robot = Robot(**data.model_dump())
        self.db.add(robot)
        health = RobotHealth(robot=robot, connectivity="offline")
        self.db.add(health)

        await self.db.flush()
        return RobotResponse.model_validate(robot)

    async def update_robot(self, robot_id: str, data: "RobotUpdate") -> Optional[RobotResponse]:
        result = await self.db.execute(select(Robot).where(Robot.id == robot_id, Robot.deleted_at.is_(None)))
        robot = result.scalar_one_or_none()
        if not robot:
            return None
        
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(robot, key, value)
            
        await self.db.flush()
        return RobotResponse.model_validate(robot)

    async def delete_robot(self, robot_id: str) -> bool:
        result = await self.db.execute(select(Robot).where(Robot.id == robot_id, Robot.deleted_at.is_(None)))
        robot = result.scalar_one_or_none()
        if not robot:
            return False
        
        robot.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()
        return True

    async def get_robot_health(self, robot_id: str) -> Optional[RobotHealthResponse]:
        result = await self.db.execute(select(RobotHealth).where(RobotHealth.robot_id == robot_id))
        health = result.scalar_one_or_none()
        return RobotHealthResponse.model_validate(health) if health else None

    async def update_robot_odom(self, robot_id: str, x: float, y: float, theta_z: float, theta_w: float, linear_v: float, angular_v: float):
        stmt = (
            update(Robot)
            .where(Robot.id == robot_id)
            .values(
                position_x=x,
                position_y=y,
                orientation_z=theta_z,
                orientation_w=theta_w,
                linear_velocity=linear_v,
                angular_velocity=angular_v,
                last_odom_at=datetime.now(timezone.utc),
            )
        )
        await self.db.execute(stmt)
        
        # Broadcast via websocket
        await manager.broadcast(
            "robot_position",
            {
                "robot_id": robot_id,
                "x": x,
                "y": y,
                "theta_z": theta_z,
                "theta_w": theta_w,
                "linear_velocity": linear_v,
                "angular_velocity": angular_v,
            }
        )

    async def send_command(self, robot_id: str, command: str, payload: dict) -> dict:
        """Forward a high-level command (emergency_stop, clear_estop, cancel_task, go_to, dock, manual_velocity) to the robot bridge."""
        from app.services.bridge_client import pool
        from app.services.live_state import live

        robot = live.find_robot(robot_id)
        if robot is None:
            raise ValueError("Robot is offline or unknown to the bridge")
        logger.info("Command %s -> robot %s %s", command, robot["robot_id"], payload if command != "manual_velocity" else "")
        result = await pool.for_robot(robot).command(robot["robot_id"], command, payload)
        await manager.broadcast("robot_command", {"robot_id": robot_id, "command": command, "result": result})
        return result
