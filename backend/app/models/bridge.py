from typing import Optional

from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class BridgeEndpoint(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A robot PC running the ROS 2 wms_bridge. Admins add/remove these from the dashboard; the backend polls every enabled one."""

    __tablename__ = "bridge_endpoints"
    __table_args__ = (UniqueConstraint("host", "port", name="uq_bridge_host_port"),)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)       # IP address or hostname
    port: Mapped[int] = mapped_column(Integer, default=8005, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    scheme: Mapped[str] = mapped_column(String(10), default="http", server_default="http", nullable=False)   # http | https (tunnels)
    token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)   # shared secret sent as X-Bridge-Token

    @property
    def url(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}"
