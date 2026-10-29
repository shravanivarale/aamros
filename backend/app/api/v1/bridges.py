"""Robot bridges (robot PCs running wms_bridge): the admin adds, tests, enables/disables and removes them from the dashboard.
The sync service picks changes up within ~2 s, so no restart or environment variable is needed to add another robot PC."""
import re
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_roles
from app.core.enums import UserRole
from app.db.session import get_db
from app.models.bridge import BridgeEndpoint
from app.models.user import User
from app.services.bridge_client import probe
from app.services.live_state import live

router = APIRouter(prefix="/bridges", tags=["Robot Bridges"])
Admin = Annotated[User, Depends(require_roles(UserRole.ADMINISTRATOR))]
HOST_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9\-\.]{0,251}[A-Za-z0-9])?$")


def _clean_host(v: str) -> str:
    v = v.strip()
    v = re.sub(r"^https?://", "", v).split("/")[0].split(":")[0]       # forgive "http://10.0.0.5:8005/"
    if not HOST_RE.match(v):
        raise ValueError("Enter an IP address (e.g. 10.113.140.148) or a hostname, without spaces or paths")
    return v


def _split_url(data: dict) -> dict:
    """Accept a pasted URL in the host field: 'https://robot.example.com' -> scheme https, port 443 (unless given)."""
    host = data.get("host")
    if isinstance(host, str):
        m = re.match(r"^(https?)://([^/:]+)(?::(\d+))?", host.strip())
        if m:
            data = dict(data, host=m.group(2), scheme=m.group(1))
            if m.group(3):
                data["port"] = int(m.group(3))
            elif m.group(1) == "https" and data.get("port") in (None, 8005):
                data["port"] = 443
    return data


class BridgeIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    host: str
    port: int = Field(default=8005, ge=1, le=65535)
    scheme: Literal["http", "https"] = "http"
    token: Optional[str] = Field(default=None, max_length=255)
    enabled: bool = True

    @model_validator(mode="before")
    @classmethod
    def _url(cls, v):
        return _split_url(v) if isinstance(v, dict) else v

    _host = field_validator("host")(lambda cls, v: _clean_host(v))


class BridgeUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    host: Optional[str] = None
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    scheme: Optional[Literal["http", "https"]] = None
    token: Optional[str] = Field(default=None, max_length=255)      # "" clears it
    enabled: Optional[bool] = None

    @model_validator(mode="before")
    @classmethod
    def _url(cls, v):
        return _split_url(v) if isinstance(v, dict) else v

    @field_validator("host")
    @classmethod
    def _host(cls, v):
        return _clean_host(v) if v is not None else v


class BridgeTest(BaseModel):
    host: str
    port: int = Field(default=8005, ge=1, le=65535)
    scheme: Literal["http", "https"] = "http"
    token: Optional[str] = Field(default=None, max_length=255)

    @model_validator(mode="before")
    @classmethod
    def _url(cls, v):
        return _split_url(v) if isinstance(v, dict) else v

    _host = field_validator("host")(lambda cls, v: _clean_host(v))


def _out(b: BridgeEndpoint) -> dict:
    ep = live.endpoints.get(b.id)
    robots = [{"robot_id": r["robot_id"], "db_id": r.get("db_id"), "status": r["status"], "localized": r.get("localized")}
              for r in live.robots.values() if r.get("endpoint_id") == b.id]
    state = "disabled" if not b.enabled else ("online" if ep and ep.online else ("offline" if ep and ep.last_error else "connecting"))
    return {"id": b.id, "name": b.name, "host": b.host, "port": b.port, "scheme": b.scheme, "has_token": bool(b.token),
            "enabled": b.enabled, "url": b.url, "state": state,
            "error": ep.last_error if ep else None, "robots": robots,
            "allow_motion": ep.health.get("allow_motion") if ep and ep.online else None,
            "map_id": ep.health.get("map_id") if ep and ep.online else None}


@router.get("")
async def list_bridges(_: Admin, db: Annotated[AsyncSession, Depends(get_db)]):
    rows = (await db.execute(select(BridgeEndpoint).order_by(BridgeEndpoint.created_at))).scalars().all()
    return [_out(b) for b in rows]


@router.post("/test")
async def test_bridge(data: BridgeTest, _: Admin):
    """Is there a wms_bridge at this address, and which robots does it report? (Nothing is saved.)"""
    return await probe(data.host, data.port, data.scheme, data.token)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_bridge(data: BridgeIn, _: Admin, db: Annotated[AsyncSession, Depends(get_db)]):
    if (await db.execute(select(BridgeEndpoint).where(BridgeEndpoint.host == data.host, BridgeEndpoint.port == data.port, BridgeEndpoint.scheme == data.scheme))).scalar_one_or_none():
        raise HTTPException(409, detail=f"{data.host}:{data.port} is already in the list")
    b = BridgeEndpoint(**{**data.model_dump(), "token": data.token or None})
    db.add(b)
    await db.commit()
    return _out(b)


@router.put("/{bridge_id}")
async def update_bridge(bridge_id: str, data: BridgeUpdate, _: Admin, db: Annotated[AsyncSession, Depends(get_db)]):
    b = (await db.execute(select(BridgeEndpoint).where(BridgeEndpoint.id == bridge_id))).scalar_one_or_none()
    if not b:
        raise HTTPException(404, detail="Bridge not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(b, k, (v or None) if k == "token" else v)
    clash = (await db.execute(select(BridgeEndpoint).where(BridgeEndpoint.host == b.host, BridgeEndpoint.port == b.port,
                                                            BridgeEndpoint.id != b.id))).scalar_one_or_none()
    if clash:
        raise HTTPException(409, detail=f"{b.host}:{b.port} is already in the list")
    await db.commit()
    return _out(b)


@router.delete("/{bridge_id}")
async def delete_bridge(bridge_id: str, _: Admin, db: Annotated[AsyncSession, Depends(get_db)]):
    b = (await db.execute(select(BridgeEndpoint).where(BridgeEndpoint.id == bridge_id))).scalar_one_or_none()
    if not b:
        raise HTTPException(404, detail="Bridge not found")
    await db.delete(b)
    await db.commit()
    return {"status": "success", "message": f"{b.host}:{b.port} removed; its robots show offline"}
