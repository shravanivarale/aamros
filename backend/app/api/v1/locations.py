"""Locations taught on the robot's map (home, receiving, shipping, charging, rack slots). The robot navigates to these."""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_roles
from app.core.enums import UserRole
from app.db.session import get_db
from app.models.location import LOCATION_KINDS, MapLocation
from app.models.map import WarehouseMap
from app.models.user import User
from app.services.live_state import live
from app.services.task_dispatch import push_locations
from app.websocket.gateway import manager

router = APIRouter(prefix="/locations", tags=["Map Locations"])
Staff = Annotated[User, Depends(require_roles(UserRole.ADMINISTRATOR, UserRole.WAREHOUSE_OPERATOR))]
Admin = Annotated[User, Depends(require_roles(UserRole.ADMINISTRATOR))]


class LocationIn(BaseModel):
    code: str = Field(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_\-\.]+$")
    kind: str = "waypoint"
    x: float
    y: float
    yaw: float = 0.0                       # radians
    label: Optional[str] = None
    rack_id: Optional[str] = None
    rack_slot_id: Optional[str] = None


class LocationUpdate(BaseModel):
    kind: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    yaw: Optional[float] = None
    label: Optional[str] = None
    rack_id: Optional[str] = None
    rack_slot_id: Optional[str] = None


class LocationOut(LocationIn):
    id: str
    map_label: Optional[str] = None
    issue: Optional[str] = None            # set when the robot refused it (on a wall, unmapped space, too close to a wall)


def _out(l: MapLocation) -> LocationOut:
    return LocationOut(id=l.id, code=l.code, kind=l.kind, x=l.x, y=l.y, yaw=l.yaw, label=l.label, rack_id=l.rack_id,
                       rack_slot_id=l.rack_slot_id, map_label=l.map_label, issue=live.location_issues.get(l.code))


def _check_kind(kind: str):
    if kind not in LOCATION_KINDS:
        raise HTTPException(422, detail=f"kind must be one of {', '.join(LOCATION_KINDS)}")


async def _changed(db: AsyncSession) -> None:
    await db.commit()
    await push_locations(db, force=True)             # the robot has the new registry (and has judged it) before we answer
    await manager.broadcast("locations_update", {"count": len((await db.execute(select(MapLocation.id))).all()),
                                                 "issues": live.location_issues})


@router.get("", response_model=list[LocationOut])
async def list_locations(_: Staff, db: Annotated[AsyncSession, Depends(get_db)]):
    rows = (await db.execute(select(MapLocation).order_by(MapLocation.kind, MapLocation.code))).scalars().all()
    return [_out(l) for l in rows]


@router.post("", response_model=LocationOut, status_code=status.HTTP_201_CREATED)
async def create_location(data: LocationIn, _: Admin, db: Annotated[AsyncSession, Depends(get_db)]):
    _check_kind(data.kind)
    if (await db.execute(select(MapLocation).where(MapLocation.code == data.code))).scalar_one_or_none():
        raise HTTPException(409, detail=f"Location {data.code} already exists")
    cur = (await db.execute(select(WarehouseMap).where(WarehouseMap.is_active == True).order_by(WarehouseMap.created_at.desc()))).scalars().first()  # noqa: E712
    loc = MapLocation(**data.model_dump(), map_label=cur.label if cur else None)
    db.add(loc)
    await _changed(db)
    return _out(loc)


@router.put("/{code}", response_model=LocationOut)
async def update_location(code: str, data: LocationUpdate, _: Admin, db: Annotated[AsyncSession, Depends(get_db)]):
    loc = (await db.execute(select(MapLocation).where(MapLocation.code == code))).scalar_one_or_none()
    if not loc:
        raise HTTPException(404, detail="Location not found")
    if data.kind:
        _check_kind(data.kind)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(loc, k, v)
    await _changed(db)
    return _out(loc)


@router.delete("/{code}")
async def delete_location(code: str, _: Admin, db: Annotated[AsyncSession, Depends(get_db)]):
    loc = (await db.execute(select(MapLocation).where(MapLocation.code == code))).scalar_one_or_none()
    if not loc:
        raise HTTPException(404, detail="Location not found")
    await db.delete(loc)
    await _changed(db)
    return {"status": "success", "message": f"Location {code} deleted"}
