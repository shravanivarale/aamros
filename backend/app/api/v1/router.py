from fastapi import APIRouter, Depends

from app.core.deps import require_roles
from app.core.enums import UserRole

from app.api.v1 import admin, assistant, auth, customer, warehouse, robots, map, slotting, robot_communication

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(assistant.router)
api_router.include_router(customer.router)
api_router.include_router(warehouse.router)
api_router.include_router(admin.router)
api_router.include_router(robots.router)
api_router.include_router(map.router)
api_router.add_api_route("/stock-movements", warehouse.list_stock_movements, methods=["GET"], tags=["Warehouse Intake"])
# Slotting endpoints read/write warehouse placement data: staff only.
api_router.include_router(
    slotting.router,
    prefix="/slotting",
    tags=["Slotting Engine"],
    dependencies=[Depends(require_roles(UserRole.ADMINISTRATOR, UserRole.WAREHOUSE_OPERATOR))],
)
api_router.include_router(robot_communication.router)

