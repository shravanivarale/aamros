from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class RobotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    model: str
    serial_number: str
    ip_address: Optional[str] = "192.168.1.12"
    status: str
    battery_level: float
    current_task_id: Optional[str] = None
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    position_z: Optional[float] = None
    orientation_z: Optional[float] = None
    orientation_w: Optional[float] = None
    linear_velocity: Optional[float] = None
    angular_velocity: Optional[float] = None
    last_odom_at: Optional[datetime] = None
    is_enabled: bool
    created_at: datetime


class RobotCreate(BaseModel):
    name: str
    model: str = "AMR-001"
    serial_number: str
    ip_address: Optional[str] = "192.168.1.12"


class RobotUpdate(BaseModel):
    name: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    ip_address: Optional[str] = None
    is_enabled: Optional[bool] = None


class RobotHealthResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    robot_id: str
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    temperature: Optional[float] = None
    connectivity: str
    error_count: int
    maintenance_due: bool


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_type: str
    status: str
    priority: int
    robot_id: Optional[str] = None
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
