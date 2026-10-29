import json
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import ShipmentStatus, TaskStatus, TaskType
from app.models.shipment import IncomingShipment, ShipmentItem
from app.models.task import RobotTask
from app.schemas.shipment import ShipmentCreate, ShipmentResponse


class ShipmentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_shipment(self, operator_id: str, data: ShipmentCreate) -> ShipmentResponse:
        items = [
            ShipmentItem(
                product_id=item.product_id,
                expected_quantity=item.expected_quantity,
                aruco_marker_id=item.aruco_marker_id,
                crate_label=item.crate_label,
            )
            for item in data.items
        ]

        shipment = IncomingShipment(
            shipment_number=f"SHP-{uuid.uuid4().hex[:8].upper()}",
            operator_id=operator_id,
            status=ShipmentStatus.QUEUED.value,
            notes=data.notes,
            items=items,
        )
        self.db.add(shipment)
        await self.db.flush()

        tasks = [
            RobotTask(
                task_type=TaskType.STORE_CRATE.value,
                status=TaskStatus.QUEUED.value,
                priority=4,
                reference_type="shipment",
                reference_id=shipment.id,
                product_id=item.product_id,
                payload=json.dumps({"shipment_number": shipment.shipment_number, "quantity": item.expected_quantity,
                                    "crate_label": item.crate_label, "aruco_marker_id": item.aruco_marker_id}),
            )
            for item in items
        ]
        self.db.add_all(tasks)
        await self.db.flush()

        shipment.task_id = tasks[0].id if tasks else None
        shipment.status = ShipmentStatus.PROCESSING.value
        await self.db.flush()

        query = select(IncomingShipment).options(selectinload(IncomingShipment.items)).where(IncomingShipment.id == shipment.id)
        result = await self.db.execute(query)
        shipment_with_items = result.scalar_one()

        return ShipmentResponse.model_validate(shipment_with_items)

    async def list_shipments(self) -> list[ShipmentResponse]:
        result = await self.db.execute(
            select(IncomingShipment)
            .options(selectinload(IncomingShipment.items))
            .order_by(IncomingShipment.created_at.desc())
        )
        return [ShipmentResponse.model_validate(s) for s in result.scalars().all()]

    async def get_shipment(self, shipment_id: str) -> Optional[ShipmentResponse]:
        result = await self.db.execute(
            select(IncomingShipment)
            .options(selectinload(IncomingShipment.items))
            .where(IncomingShipment.id == shipment_id)
        )
        shipment = result.scalar_one_or_none()
        return ShipmentResponse.model_validate(shipment) if shipment else None
