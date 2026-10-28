"""Seed a connected demo warehouse dataset for local or Supabase databases."""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.enums import OrderStatus, RobotStatus, ShipmentStatus, TaskStatus, TaskType, UserRole
from app.core.security import get_password_hash
from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
from app.models.inventory import InventoryEvent, InventoryItem
from app.models.order import CustomerOrder, OrderItem
from app.models.robot import Robot, RobotHealth
from app.models.shipment import IncomingShipment, ShipmentItem
from app.models.task import RobotTask
from app.models.user import User
from app.models.warehouse import Product, ProductCategory, Rack, Shelf, WarehouseZone

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger("seed_demo")


async def one(db, model, **filters):
    result = await db.execute(select(model).where(*(getattr(model, key) == value for key, value in filters.items())))
    return result.scalar_one_or_none()


async def seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        users = {
            "admin": await one(db, User, email="admin@robu.io"),
            "operator": await one(db, User, email="operator@robu.io"),
            "customer": await one(db, User, email="customer@robu.io"),
        }
        user_specs = {
            "admin": ("admin@robu.io", "admin12345", "System Administrator", UserRole.ADMINISTRATOR.value),
            "operator": ("operator@robu.io", "operator123", "Warehouse Operator", UserRole.WAREHOUSE_OPERATOR.value),
            "customer": ("customer@robu.io", "customer123", "Demo Customer", UserRole.CUSTOMER.value),
        }
        for key, (email, password, name, role) in user_specs.items():
            if users[key] is None:
                users[key] = User(email=email, hashed_password=get_password_hash(password), full_name=name, role=role)
                db.add(users[key])
        await db.flush()

        category_specs = [
            ("Electronics", "Sensors, controllers, and electronic modules"),
            ("Mechanical", "Fasteners, brackets, and mechanical components"),
            ("Packaging", "Crates, labels, and warehouse packaging supplies"),
        ]
        categories = {}
        for name, description in category_specs:
            category = await one(db, ProductCategory, name=name)
            if category is None:
                category = ProductCategory(name=name, description=description)
                db.add(category)
                await db.flush()
            categories[name] = category

        product_specs = [
            ("SKU-001", "Microcontroller Board", "Electronics", 29.99, 0.18, "A", "X", 92),
            ("SKU-002", "Sensor Module Kit", "Electronics", 49.99, 0.24, "A", "Y", 88),
            ("SKU-003", "Motor Driver Unit", "Electronics", 79.99, 0.42, "B", "X", 76),
            ("MECH-101", "M3 Screw Set", "Mechanical", 5.99, 0.20, "C", "X", 54),
            ("MECH-204", "Aluminium Mounting Bracket", "Mechanical", 18.50, 0.65, "B", "Y", 68),
            ("MECH-310", "Conveyor Roller", "Mechanical", 124.00, 4.80, "A", "Z", 84),
            ("PACK-401", "Reusable Storage Crate", "Packaging", 32.00, 1.10, "B", "X", 61),
            ("PACK-402", "Barcode Label Roll", "Packaging", 12.50, 0.30, "C", "Y", 47),
            ("PACK-403", "Pallet Wrap Film", "Packaging", 26.75, 2.40, "C", "X", 39),
        ]
        products = {}
        for sku, name, category_name, price, weight, abc, xyz, priority in product_specs:
            product = await one(db, Product, sku=sku)
            if product is None:
                product = Product(sku=sku, name=name, category_id=categories[category_name].id)
                db.add(product)
            product.name = name
            product.category_id = categories[category_name].id
            product.unit_price = price
            product.weight_kg = weight
            product.height = 25.0
            product.width = 15.0
            product.depth = 10.0
            product.volume = 3750.0
            product.abc_class = abc
            product.xyz_class = xyz
            product.priority_score = priority
            products[sku] = product
        await db.flush()

        zone_specs = [
            ("Receiving", "intake"),
            ("High Velocity Storage", "storage"),
            ("Bulk Storage", "storage"),
            ("Shipping Bay", "shipping"),
        ]
        zones = {}
        for name, zone_type in zone_specs:
            zone = await one(db, WarehouseZone, name=name)
            if zone is None:
                zone = WarehouseZone(name=name, zone_type=zone_type, description=f"Demo {zone_type} area")
                db.add(zone)
                await db.flush()
            zones[name] = zone

        rack_specs = [("R-A1", "High Velocity Storage"), ("R-B1", "Bulk Storage"), ("R-S1", "Shipping Bay")]
        racks = {}
        for code, zone_name in rack_specs:
            rack = await one(db, Rack, code=code)
            if rack is None:
                rack = Rack(code=code, zone_id=zones[zone_name].id, capacity=24)
                db.add(rack)
                await db.flush()
            racks[code] = rack

        shelf_specs = [("R-A1-L1", "R-A1", 1), ("R-A1-L2", "R-A1", 2), ("R-B1-L1", "R-B1", 1), ("R-S1-L1", "R-S1", 1)]
        shelves = {}
        for code, rack_code, level in shelf_specs:
            shelf = await one(db, Shelf, code=code)
            if shelf is None:
                shelf = Shelf(code=code, rack_id=racks[rack_code].id, level=level, capacity=1000)
                db.add(shelf)
                await db.flush()
            shelves[code] = shelf

        stock_specs = [
            ("SKU-001", "R-A1-L1", 148, 18, 11),
            ("SKU-002", "R-A1-L2", 86, 12, 12),
            ("SKU-003", "R-A1-L2", 54, 6, 13),
            ("MECH-101", "R-B1-L1", 620, 40, 21),
            ("MECH-204", "R-B1-L1", 72, 8, 22),
            ("MECH-310", "R-B1-L1", 18, 2, 23),
            ("PACK-401", "R-S1-L1", 44, 5, 31),
            ("PACK-402", "R-S1-L1", 210, 25, 32),
            ("PACK-403", "R-S1-L1", 96, 10, 33),
        ]
        inventory = {}
        for sku, shelf_code, quantity, reserved, marker in stock_specs:
            item = await one(db, InventoryItem, product_id=products[sku].id)
            if item is None:
                item = InventoryItem(product_id=products[sku].id)
                db.add(item)
            item.shelf_id = shelves[shelf_code].id
            item.quantity = quantity
            item.reserved_quantity = reserved
            item.aruco_marker_id = marker
            item.source = "demo_seed"
            inventory[sku] = item
        await db.flush()

        robot_specs = [
            ("AMR-Alpha", "ROBU-001", RobotStatus.BUSY.value, 82.0),
            ("AMR-Beta", "ROBU-002", RobotStatus.IDLE.value, 96.0),
            ("AMR-Gamma", "ROBU-003", RobotStatus.CHARGING.value, 38.0),
        ]
        robots = {}
        for name, serial, robot_status, battery in robot_specs:
            robot = await one(db, Robot, name=name)
            if robot is None:
                robot = Robot(name=name, serial_number=serial)
                db.add(robot)
                await db.flush()
            robot.status = robot_status
            robot.battery_level = battery
            robot.position_x = 2.0 if name == "AMR-Alpha" else 6.0
            robot.position_y = 3.0 if name == "AMR-Alpha" else 1.0
            robots[name] = robot
            health = await one(db, RobotHealth, robot_id=robot.id)
            if health is None:
                db.add(RobotHealth(robot_id=robot.id, connectivity="online" if robot_status != "charging" else "online"))
        await db.flush()

        order_specs = [
            ("ORD-DEMO-1001", OrderStatus.PENDING.value, "SKU-001", 3, None, "Waiting for robot assignment"),
            ("ORD-DEMO-1002", OrderStatus.CONFIRMED.value, "SKU-002", 5, "AMR-Beta", "Confirmed for morning dispatch"),
            ("ORD-DEMO-1003", OrderStatus.PROCESSING.value, "MECH-204", 2, "AMR-Alpha", "Picking in progress"),
            ("ORD-DEMO-1004", OrderStatus.RETRIEVING.value, "SKU-003", 1, "AMR-Alpha", "Robot retrieving from high velocity storage"),
            ("ORD-DEMO-1005", OrderStatus.READY.value, "PACK-401", 4, "AMR-Beta", "Ready at shipping bay"),
            ("ORD-DEMO-1006", OrderStatus.DELIVERED.value, "MECH-101", 20, "AMR-Beta", "Delivered to demo customer"),
        ]
        orders = {}
        for number, order_status, sku, quantity, robot_name, notes in order_specs:
            order = await one(db, CustomerOrder, order_number=number)
            if order is None:
                order = CustomerOrder(order_number=number, customer_id=users["customer"].id)
                db.add(order)
                await db.flush()
                db.add(OrderItem(order_id=order.id, product_id=products[sku].id, quantity=quantity, unit_price=products[sku].unit_price))
            order.status = order_status
            order.total_amount = round(products[sku].unit_price * quantity, 2)
            order.assigned_robot_id = robots[robot_name].id if robot_name else None
            order.notes = notes
            orders[number] = order

        shipment_specs = [
            ("SHP-DEMO-2001", ShipmentStatus.REGISTERED.value, "PACK-402", 60, None, "New label stock awaiting intake"),
            ("SHP-DEMO-2002", ShipmentStatus.QUEUED.value, "MECH-310", 12, "AMR-Beta", "Queued for putaway"),
            ("SHP-DEMO-2003", ShipmentStatus.PROCESSING.value, "SKU-002", 40, "AMR-Alpha", "Being verified at receiving"),
            ("SHP-DEMO-2004", ShipmentStatus.COMPLETED.value, "SKU-001", 80, "AMR-Beta", "Putaway completed"),
        ]
        for number, shipment_status, sku, quantity, robot_name, notes in shipment_specs:
            shipment = await one(db, IncomingShipment, shipment_number=number)
            if shipment is None:
                shipment = IncomingShipment(shipment_number=number, operator_id=users["operator"].id)
                db.add(shipment)
                await db.flush()
                db.add(ShipmentItem(shipment_id=shipment.id, product_id=products[sku].id, expected_quantity=quantity, crate_label=f"CRATE-{number[-4:]}"))
            shipment.status = shipment_status
            shipment.assigned_robot_id = robots[robot_name].id if robot_name else None
            shipment.notes = notes

        task_specs = [
            ("TASK-DEMO-3001", TaskType.RETRIEVE_PRODUCT.value, TaskStatus.IN_PROGRESS.value, "AMR-Alpha", "SKU-003", "Order ORD-DEMO-1004"),
            ("TASK-DEMO-3002", TaskType.STORE_CRATE.value, TaskStatus.QUEUED.value, "AMR-Beta", "MECH-310", "Shipment SHP-DEMO-2002"),
            ("TASK-DEMO-3003", TaskType.VERIFY_INVENTORY.value, TaskStatus.COMPLETED.value, "AMR-Beta", "SKU-001", "Cycle count completed"),
        ]
        for reference_id, task_type, task_status, robot_name, sku, reason in task_specs:
            task = await one(db, RobotTask, reference_id=reference_id)
            if task is None:
                db.add(RobotTask(
                    reference_id=reference_id,
                    task_type=task_type,
                    status=task_status,
                    priority=3,
                    robot_id=robots[robot_name].id,
                    product_id=products[sku].id,
                    reason=reason,
                ))

        movement_specs = [
            ("SKU-001", 80, "putaway", "Receiving dock to high velocity storage"),
            ("SKU-002", 40, "putaway", "Receiving dock to high velocity storage"),
            ("MECH-101", -20, "pick", "Bulk storage to shipping bay"),
            ("MECH-204", -2, "pick", "Bulk storage to shipping bay"),
            ("PACK-402", 60, "putaway", "Receiving dock to shipping supplies"),
            ("SKU-003", -1, "relocation", "High velocity storage cycle count"),
        ]
        existing_events = await db.execute(select(InventoryEvent).where(InventoryEvent.notes.like("Demo telemetry:%")))
        if not existing_events.scalars().first():
            for index, (sku, quantity_change, event_type, note) in enumerate(movement_specs):
                db.add(InventoryEvent(
                    product_id=products[sku].id,
                    inventory_item_id=inventory[sku].id,
                    event_type=event_type,
                    quantity_change=quantity_change,
                    robot_id=robots["AMR-Alpha" if index % 2 == 0 else "AMR-Beta"].id,
                    notes=f"Demo telemetry: {note}",
                ))

        await db.commit()
        logger.info("Demo data is ready: %d products, %d orders, %d shipments, %d robots.", len(products), len(order_specs), len(shipment_specs), len(robots))


if __name__ == "__main__":
    try:
        asyncio.run(seed())
    except Exception as exc:  # noqa: BLE001
        logger.exception("Demo seeding failed: %s", exc)
        sys.exit(1)