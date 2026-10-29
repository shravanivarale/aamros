"""HTTP clients for the ROS 2 robot bridges (armsbot_nav wms_bridge): one per robot PC. The only place the backend talks to robots."""
import logging
from typing import Any, Optional

import httpx

from app.services.live_state import EndpointState, live

logger = logging.getLogger(__name__)
PREFIX = "/api/v1/robot-communication"


class BridgeOffline(Exception):
    """A bridge could not be reached (robot PC off, wrong address, network)."""


class BridgeClient:
    def __init__(self, base_url: str, token: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.token = token or None
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def headers(self) -> dict[str, str]:
        return {"X-Bridge-Token": self.token} if self.token else {}

    def _c(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(3.0, connect=1.5), headers=self.headers)
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def request(self, method: str, path: str, json: Any = None, params: Optional[dict] = None) -> Any:
        url = f"{self.base_url}{PREFIX}{path}"
        try:
            r = await self._c().request(method, url, json=json, params=params)
        except httpx.RequestError as exc:
            raise BridgeOffline(f"{url}: {exc.__class__.__name__}") from exc
        if r.status_code >= 400:
            raise httpx.HTTPStatusError(f"{r.status_code} {r.text[:200]}", request=r.request, response=r)
        return r.json() if r.content else None

    async def get(self, path: str, **params) -> Any:
        return await self.request("GET", path, params=params or None)

    async def post(self, path: str, json: Any = None) -> Any:
        return await self.request("POST", path, json=json if json is not None else {})

    async def health(self) -> dict:
        return await self.get("/health")

    async def robots(self) -> list[dict]:
        return await self.get("/robots")

    async def events_since(self, seq: int) -> list[dict]:
        return await self.get("/events", since=seq)

    async def command(self, robot_id: str, command: str, payload: Optional[dict] = None) -> dict:
        return await self.post(f"/robots/{robot_id}/command", {"command": command, "payload": payload or {}})


class BridgePool:
    """One BridgeClient per endpoint id (re-created if the admin changes its address)."""

    def __init__(self):
        self._clients: dict[str, BridgeClient] = {}

    def client(self, ep: EndpointState) -> BridgeClient:
        c = self._clients.get(ep.id)
        if c is None or c.base_url != ep.url.rstrip("/") or c.token != (ep.token or None):
            c = self._clients[ep.id] = BridgeClient(ep.url, ep.token)
        return c

    def for_robot(self, robot: dict) -> BridgeClient:
        ep = live.endpoint_of(robot)
        if ep is None:
            raise BridgeOffline("robot's bridge is no longer configured")
        return self.client(ep)

    def online(self) -> list[tuple[EndpointState, BridgeClient]]:
        return [(e, self.client(e)) for e in live.endpoints.values() if e.online]

    async def drop(self, endpoint_id: str):
        c = self._clients.pop(endpoint_id, None)
        if c:
            await c.close()

    async def close(self):
        for c in list(self._clients.values()):
            await c.close()
        self._clients.clear()


pool = BridgePool()


async def probe(host: str, port: int, scheme: str = "http", token: Optional[str] = None) -> dict[str, Any]:
    """One-off reachability check of a candidate bridge (used by the dashboard's 'Test' button before saving)."""
    c = BridgeClient(f"{scheme}://{host}:{port}", token)
    try:
        h = await c.health()
        robots = await c.robots()
        return {"reachable": True, "error": None, "allow_motion": h.get("allow_motion"), "map_id": h.get("map_id"),
                "started_at": h.get("started_at"), "localized": h.get("localized"),
                "robots": [{"robot_id": r.get("robot_id"), "status": r.get("status"), "localized": r.get("localized")} for r in robots]}
    except BridgeOffline as exc:
        return {"reachable": False, "error": str(exc)}
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            return {"reachable": False, "error": "the bridge is there but refused the token (wrong or missing API token)"}
        return {"reachable": False, "error": f"answered, but not like a wms_bridge: {exc}"}
    except Exception as exc:                                    # noqa: BLE001  (reachable but not a wms_bridge, bad JSON)
        return {"reachable": False, "error": f"answered, but not like a wms_bridge: {exc}"}
    finally:
        await c.close()
