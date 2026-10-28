from enum import Enum


class UserRole(str, Enum):
    CUSTOMER = "customer"
    WAREHOUSE_OPERATOR = "warehouse_operator"
    ADMINISTRATOR = "administrator"
    SYSTEM = "system"


class RobotStatus(str, Enum):
    IDLE = "idle"
    BUSY = "busy"
    NAVIGATING = "navigating"
    CHARGING = "charging"
    OFFLINE = "offline"
    ERROR = "error"
    EMERGENCY_STOP = "emergency_stop"


class TaskType(str, Enum):
    STORE_CRATE = "store_crate"
    RETRIEVE_PRODUCT = "retrieve_product"
    VERIFY_INVENTORY = "verify_inventory"
    PATROL_WAREHOUSE = "patrol_warehouse"
    RETURN_TO_DOCK = "return_to_dock"
    INVENTORY_AUDIT = "inventory_audit"


class TaskStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    RETRIEVING = "retrieving"
    READY = "ready"
    COMPLETED = "completed"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class ShipmentStatus(str, Enum):
    REGISTERED = "registered"
    QUEUED = "queued"
    PROCESSING = "processing"
    STORING = "storing"
    COMPLETED = "completed"
    FAILED = "failed"


class RobotEventType(str, Enum):
    TASK_ACCEPTED = "task_accepted"
    NAVIGATION_STARTED = "navigation_started"
    MARKER_DETECTED = "marker_detected"
    PRODUCT_REGISTERED = "product_registered"
    PLACEMENT_VERIFIED = "placement_verified"
    RETRIEVAL_COMPLETED = "retrieval_completed"
    DELIVERY_COMPLETED = "delivery_completed"
    INVENTORY_UPDATED = "inventory_updated"
    TASK_FAILED = "task_failed"
    BATTERY_LOW = "battery_low"
    DOCKING_INITIATED = "docking_initiated"
    MISSION_COMPLETED = "mission_completed"


class RobotCommandType(str, Enum):
    GO_TO = "go_to"
    DOCK = "dock"
    EMERGENCY_STOP = "emergency_stop"
    MANUAL_VELOCITY = "manual_velocity"
    CANCEL_TASK = "cancel_task"
