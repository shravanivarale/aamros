from typing import Optional

from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

LOCATION_KINDS = ("home", "receiving", "shipping", "charging", "rack_slot", "waypoint")


class MapLocation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A named point TAUGHT on the robot's real map (map frame, metres / radians).

    The robot bridge navigates to these. `code` is what tasks refer to (HOME, RECV-1, SHIP-11, RACK-1 ...). A rack_slot
    location may link to the warehouse rack / slot rows so orders and shipments can find where stock lives.
    """

    __tablename__ = "map_locations"

    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(30), default="waypoint", nullable=False)
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)
    yaw: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)       # radians, the heading the robot ends with
    label: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    rack_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    rack_slot_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    map_label: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # which map it was taught on
