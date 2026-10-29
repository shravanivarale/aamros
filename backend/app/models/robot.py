from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import RobotStatus
from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.task import RobotTask


class Robot(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "robots"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    model: Mapped[str] = mapped_column(String(100), default="AMR-001", nullable=False)
    serial_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), default="192.168.1.12", nullable=True)
    status: Mapped[str] = mapped_column(String(50), default=RobotStatus.OFFLINE.value, nullable=False)
    battery_level: Mapped[float] = mapped_column(Float, default=-1.0, nullable=False)   # percent; -1 = not measured by this robot
    current_task_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    position_x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    position_y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    position_z: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    orientation_z: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    orientation_w: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    linear_velocity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    angular_velocity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_odom_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    health: Mapped[Optional["RobotHealth"]] = relationship(back_populates="robot", uselist=False)
    tasks: Mapped[List["RobotTask"]] = relationship(back_populates="robot")


class RobotHealth(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "robot_health"

    robot_id: Mapped[str] = mapped_column(ForeignKey("robots.id"), unique=True, nullable=False)
    cpu_usage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    memory_usage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    connectivity: Mapped[str] = mapped_column(String(50), default="unknown", nullable=False)
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    maintenance_due: Mapped[bool] = mapped_column(default=False, nullable=False)

    robot: Mapped["Robot"] = relationship(back_populates="health")
