from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_roles
from app.core.enums import UserRole
from app.db.session import get_db
from app.models.user import User
from app.schemas.robot import RobotCreate, RobotHealthResponse, RobotResponse, RobotUpdate
from app.services.bridge_client import BridgeOffline
from app.services.robot_service import RobotService

router = APIRouter(prefix="/robots", tags=["Robotics Operations"])


class OdomUpdate(BaseModel):
    x: float
    y: float
    theta_z: float
    theta_w: float
    linear_v: float
    angular_v: float


class CommandRequest(BaseModel):
    command: str
    payload: dict


@router.get("", response_model=list[RobotResponse])
async def list_robots(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMINISTRATOR, UserRole.WAREHOUSE_OPERATOR))],
):
    service = RobotService(db)
    return await service.list_robots()


@router.post("", response_model=RobotResponse, status_code=status.HTTP_201_CREATED)
async def create_robot(
    data: RobotCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMINISTRATOR))],
):
    service = RobotService(db)
    return await service.create_robot(data)


@router.put("/{robot_id}", response_model=RobotResponse)
async def update_robot(
    robot_id: str,
    data: RobotUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMINISTRATOR))],
):
    service = RobotService(db)
    robot = await service.update_robot(robot_id, data)
    if not robot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Robot not found")
    return robot


@router.delete("/{robot_id}", status_code=status.HTTP_200_OK)
async def delete_robot(
    robot_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMINISTRATOR))],
):
    service = RobotService(db)
    success = await service.delete_robot(robot_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Robot not found")
    return {"status": "success", "message": "Robot deleted successfully"}


@router.get("/{robot_id}/health", response_model=RobotHealthResponse)
async def get_robot_health(
    robot_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMINISTRATOR, UserRole.WAREHOUSE_OPERATOR))],
):
    service = RobotService(db)
    health = await service.get_robot_health(robot_id)
    if not health:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Robot health not found")
    return health


@router.post("/{robot_id}/odom", status_code=status.HTTP_204_NO_CONTENT)
async def update_robot_odom(
    robot_id: str,
    data: OdomUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.SYSTEM, UserRole.ADMINISTRATOR))],
):
    service = RobotService(db)
    await service.update_robot_odom(
        robot_id, data.x, data.y, data.theta_z, data.theta_w, data.linear_v, data.angular_v
    )


@router.post("/{robot_id}/command", status_code=status.HTTP_202_ACCEPTED)
async def send_command(
    robot_id: str,
    data: CommandRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_roles(UserRole.ADMINISTRATOR, UserRole.WAREHOUSE_OPERATOR))],
):
    service = RobotService(db)
    try:
        return {"status": "command_sent", "result": await service.send_command(robot_id, data.command, data.payload)}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except BridgeOffline as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Robot bridge unreachable ({exc})")
