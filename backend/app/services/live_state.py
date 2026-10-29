"""In-memory view of every robot bridge, refreshed by robot_sync (the DB gets the durable subset)."""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class EndpointState:
    id: str
    name: str
    url: str
    token: Optional[str] = None
    online: bool = False
    last_error: Optional[str] = None
    health: dict[str, Any] = field(default_factory=dict)
    event_cursor: int = 0
    cursor_loaded: bool = False
    started_at: Optional[str] = None                 # the bridge's own start time: a change means it restarted
    locations_hash: Optional[str] = None
    location_issues: dict[str, str] = field(default_factory=dict)   # location code -> why this robot rejected it
    next_poll: float = 0.0                           # monotonic; pushed out while the bridge is unreachable
    t_health: float = 0.0
    t_events: float = 0.0


@dataclass
class LiveState:
    endpoints: dict[str, EndpointState] = field(default_factory=dict)
    robots: dict[str, dict[str, Any]] = field(default_factory=dict)   # "<endpoint id>/<bridge robot id>" -> latest bridge state

    @property
    def online(self) -> bool:
        return any(e.online for e in self.endpoints.values())

    @property
    def health(self) -> dict[str, Any]:
        return next((e.health for e in self.endpoints.values() if e.online and e.health), {})

    @property
    def location_issues(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for e in self.endpoints.values():
            out.update(e.location_issues)
        return out

    def find_robot(self, ref: Optional[str]) -> Optional[dict[str, Any]]:
        """Look a robot up by DB id, bridge robot id or '<endpoint>/<robot>' key."""
        if not ref:
            return None
        for key, r in self.robots.items():
            if ref in (key, r.get("robot_id"), r.get("db_id")):
                return r
        return None

    def endpoint_of(self, robot: dict[str, Any]) -> Optional[EndpointState]:
        return self.endpoints.get(robot.get("endpoint_id", ""))

    def snapshot(self) -> dict[str, Any]:
        return {
            "bridge_online": self.online,
            "bridge_error": next((e.last_error for e in self.endpoints.values() if e.last_error), None) if not self.online else None,
            "bridges": [{"id": e.id, "name": e.name, "url": e.url, "online": e.online, "error": e.last_error,
                         "allow_motion": e.health.get("allow_motion"), "map_id": e.health.get("map_id")} for e in self.endpoints.values()],
            "health": self.health,
            "robots": list(self.robots.values()),
        }


live = LiveState()
