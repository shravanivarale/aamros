-- ARMS demo schema and data for Supabase SQL Editor.
-- Run this whole script in Supabase Dashboard > SQL Editor.
-- It is safe to run more than once because demo rows use stable keys.

create extension if not exists pgcrypto;

create table if not exists users (
  id text primary key default gen_random_uuid()::text,
  email varchar(255) unique not null,
  hashed_password varchar(255) not null,
  full_name varchar(255) not null,
  role varchar(50) not null default 'customer',
  is_active boolean not null default true,
  phone varchar(50),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);

create table if not exists product_categories (
  id text primary key default gen_random_uuid()::text,
  name varchar(100) unique not null,
  description text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);

create table if not exists products (
  id text primary key default gen_random_uuid()::text,
  sku varchar(100) unique not null,
  name varchar(255) not null,
  description text,
  category_id text references product_categories(id),
  unit_price double precision not null default 0,
  weight_kg double precision,
  height double precision,
  width double precision,
  depth double precision,
  volume double precision,
  abc_class varchar(1),
  xyz_class varchar(1),
  priority_score double precision,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);

create table if not exists warehouse_zones (
  id text primary key default gen_random_uuid()::text,
  name varchar(100) unique not null,
  zone_type varchar(50) not null,
  description text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);

create table if not exists racks (
  id text primary key default gen_random_uuid()::text,
  code varchar(50) unique not null,
  zone_id text not null references warehouse_zones(id),
  position_x double precision,
  position_y double precision,
  capacity integer not null default 10,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);

create table if not exists shelves (
  id text primary key default gen_random_uuid()::text,
  code varchar(50) unique not null,
  rack_id text not null references racks(id),
  level integer not null default 1,
  capacity integer not null default 5,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);

create table if not exists robots (
  id text primary key default gen_random_uuid()::text,
  name varchar(100) unique not null,
  model varchar(100) not null default 'AMR-001',
  serial_number varchar(100) unique not null,
  ip_address varchar(50),
  status varchar(50) not null default 'offline',
  battery_level double precision not null default 100,
  current_task_id varchar(36),
  position_x double precision,
  position_y double precision,
  position_z double precision,
  orientation_z double precision,
  orientation_w double precision,
  linear_velocity double precision,
  angular_velocity double precision,
  last_odom_at timestamptz,
  is_enabled boolean not null default true,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);

create table if not exists robot_health (
  id text primary key default gen_random_uuid()::text,
  robot_id text unique not null references robots(id),
  cpu_usage double precision,
  memory_usage double precision,
  temperature double precision,
  connectivity varchar(50) not null default 'unknown',
  last_heartbeat timestamptz,
  error_count integer not null default 0,
  maintenance_due boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists inventory_items (
  id text primary key default gen_random_uuid()::text,
  product_id text not null references products(id),
  shelf_id text references shelves(id),
  quantity integer not null default 0,
  reserved_quantity integer not null default 0,
  aruco_marker_id integer,
  last_verified_at varchar(50),
  last_verified_by_robot_id varchar(36),
  source varchar(50) not null default 'robot_observation',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists customer_orders (
  id text primary key default gen_random_uuid()::text,
  order_number varchar(50) unique not null,
  customer_id text not null references users(id),
  status varchar(50) not null default 'pending',
  total_amount double precision not null default 0,
  assigned_robot_id varchar(36),
  task_id varchar(36),
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists order_items (
  id text primary key default gen_random_uuid()::text,
  order_id text not null references customer_orders(id) on delete cascade,
  product_id text not null references products(id),
  quantity integer not null,
  unit_price double precision not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists incoming_shipments (
  id text primary key default gen_random_uuid()::text,
  shipment_number varchar(50) unique not null,
  operator_id text not null references users(id),
  status varchar(50) not null default 'registered',
  assigned_robot_id varchar(36),
  task_id varchar(36),
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists shipment_items (
  id text primary key default gen_random_uuid()::text,
  shipment_id text not null references incoming_shipments(id) on delete cascade,
  product_id text references products(id),
  expected_quantity integer not null default 1,
  aruco_marker_id integer,
  crate_label varchar(100),
  status varchar(50) not null default 'pending',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists inventory_events (
  id text primary key default gen_random_uuid()::text,
  product_id text not null references products(id),
  inventory_item_id text references inventory_items(id),
  event_type varchar(50) not null,
  quantity_change integer not null default 0,
  robot_id varchar(36),
  task_id varchar(36),
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists robot_tasks (
  id text primary key default gen_random_uuid()::text,
  task_type varchar(50) not null default 'store_crate',
  status varchar(50) not null default 'pending',
  priority integer not null default 5,
  robot_id text references robots(id),
  reference_type varchar(50),
  reference_id varchar(36) unique,
  payload text,
  error_message text,
  product_id text references products(id),
  source_slot text,
  destination_slot text,
  estimated_distance double precision,
  estimated_time double precision,
  reason text,
  started_at varchar(50),
  completed_at varchar(50),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

insert into users (email, hashed_password, full_name, role)
values
  ('admin@robu.io', '$2b$12$5GQgH22zQDNNPl3RyLDNneeyHGtKv/uZRwPXDS6/CxiNQ2ZwOXRK2', 'System Administrator', 'administrator'),
  ('operator@robu.io', '$2b$12$7RbfhfKc.twEJ1G.bag4FecS50UL/s/DcAJeJmbk4Zz1nqel9wH6K', 'Warehouse Operator', 'warehouse_operator'),
  ('customer@robu.io', '$2b$12$MS5n7llly45R82iCngt5gekTBZodyjN8vp5CVYSVlDzToX7JPS276', 'Demo Customer', 'customer')
on conflict (email) do nothing;

insert into product_categories (name, description) values
  ('Electronics', 'Sensors, controllers, and electronic modules'),
  ('Mechanical', 'Fasteners, brackets, and mechanical components'),
  ('Packaging', 'Crates, labels, and warehouse packaging supplies')
on conflict (name) do nothing;

insert into products (sku, name, category_id, unit_price, weight_kg, height, width, depth, volume, abc_class, xyz_class, priority_score)
select v.sku, v.name, c.id, v.price, v.weight, 25, 15, 10, 3750, v.abc, v.xyz, v.priority
from (values
  ('SKU-001','Microcontroller Board','Electronics',29.99,0.18,'A','X',92),
  ('SKU-002','Sensor Module Kit','Electronics',49.99,0.24,'A','Y',88),
  ('SKU-003','Motor Driver Unit','Electronics',79.99,0.42,'B','X',76),
  ('MECH-101','M3 Screw Set','Mechanical',5.99,0.20,'C','X',54),
  ('MECH-204','Aluminium Mounting Bracket','Mechanical',18.50,0.65,'B','Y',68),
  ('MECH-310','Conveyor Roller','Mechanical',124.00,4.80,'A','Z',84),
  ('PACK-401','Reusable Storage Crate','Packaging',32.00,1.10,'B','X',61),
  ('PACK-402','Barcode Label Roll','Packaging',12.50,0.30,'C','Y',47),
  ('PACK-403','Pallet Wrap Film','Packaging',26.75,2.40,'C','X',39)
) as v(sku,name,category,price,weight,abc,xyz,priority)
join product_categories c on c.name = v.category
on conflict (sku) do update set name=excluded.name, category_id=excluded.category_id, unit_price=excluded.unit_price, weight_kg=excluded.weight_kg, abc_class=excluded.abc_class, xyz_class=excluded.xyz_class, priority_score=excluded.priority_score;

insert into warehouse_zones (name, zone_type, description) values
  ('Receiving','intake','Demo receiving area'),
  ('High Velocity Storage','storage','Demo high velocity area'),
  ('Bulk Storage','storage','Demo bulk storage area'),
  ('Shipping Bay','shipping','Demo outbound area')
on conflict (name) do nothing;

insert into racks (code, zone_id, capacity)
select v.code, z.id, 24 from (values ('R-A1','High Velocity Storage'),('R-B1','Bulk Storage'),('R-S1','Shipping Bay')) v(code,zone_name)
join warehouse_zones z on z.name=v.zone_name
on conflict (code) do nothing;

insert into shelves (code, rack_id, level, capacity)
select v.code, r.id, v.level, 1000 from (values ('R-A1-L1','R-A1',1),('R-A1-L2','R-A1',2),('R-B1-L1','R-B1',1),('R-S1-L1','R-S1',1)) v(code,rack_code,level)
join racks r on r.code=v.rack_code
on conflict (code) do nothing;

insert into robots (name, serial_number, status, battery_level, position_x, position_y)
values ('AMR-Alpha','ROBU-001','busy',82,2,3), ('AMR-Beta','ROBU-002','idle',96,6,1), ('AMR-Gamma','ROBU-003','charging',38,6,1)
on conflict (name) do update set status=excluded.status, battery_level=excluded.battery_level;

insert into robot_health (robot_id, connectivity)
select id, 'online' from robots where name in ('AMR-Alpha','AMR-Beta','AMR-Gamma')
on conflict (robot_id) do nothing;

insert into inventory_items (product_id, shelf_id, quantity, reserved_quantity, aruco_marker_id, source)
select p.id, s.id, v.quantity, v.reserved, v.marker, 'supabase_demo'
from (values
  ('SKU-001','R-A1-L1',148,18,11),('SKU-002','R-A1-L2',86,12,12),('SKU-003','R-A1-L2',54,6,13),
  ('MECH-101','R-B1-L1',620,40,21),('MECH-204','R-B1-L1',72,8,22),('MECH-310','R-B1-L1',18,2,23),
  ('PACK-401','R-S1-L1',44,5,31),('PACK-402','R-S1-L1',210,25,32),('PACK-403','R-S1-L1',96,10,33)
) v(sku,shelf_code,quantity,reserved,marker)
join products p on p.sku=v.sku join shelves s on s.code=v.shelf_code
where not exists (select 1 from inventory_items i where i.product_id=p.id);

insert into customer_orders (order_number, customer_id, status, total_amount, assigned_robot_id, notes)
select v.number, u.id, v.status, p.unit_price*v.quantity, r.id, v.notes
from (values
  ('ORD-DEMO-1001','pending','SKU-001',3,null,'Waiting for robot assignment'),
  ('ORD-DEMO-1002','confirmed','SKU-002',5,'AMR-Beta','Confirmed for morning dispatch'),
  ('ORD-DEMO-1003','processing','MECH-204',2,'AMR-Alpha','Picking in progress'),
  ('ORD-DEMO-1004','retrieving','SKU-003',1,'AMR-Alpha','Robot retrieving from storage'),
  ('ORD-DEMO-1005','ready','PACK-401',4,'AMR-Beta','Ready at shipping bay'),
  ('ORD-DEMO-1006','delivered','MECH-101',20,'AMR-Beta','Delivered to demo customer')
) v(number,status,sku,quantity,robot_name,notes)
join users u on u.email='customer@robu.io' join products p on p.sku=v.sku left join robots r on r.name=v.robot_name
on conflict (order_number) do nothing;

insert into order_items (order_id, product_id, quantity, unit_price)
select o.id, p.id, v.quantity, p.unit_price
from (values ('ORD-DEMO-1001','SKU-001',3),('ORD-DEMO-1002','SKU-002',5),('ORD-DEMO-1003','MECH-204',2),('ORD-DEMO-1004','SKU-003',1),('ORD-DEMO-1005','PACK-401',4),('ORD-DEMO-1006','MECH-101',20)) v(order_number,sku,quantity)
join customer_orders o on o.order_number=v.order_number join products p on p.sku=v.sku
where not exists (select 1 from order_items i where i.order_id=o.id and i.product_id=p.id);

insert into incoming_shipments (shipment_number, operator_id, status, assigned_robot_id, notes)
select v.number, u.id, v.status, r.id, v.notes
from (values
  ('SHP-DEMO-2001','registered','PACK-402',null,'New label stock awaiting intake'),
  ('SHP-DEMO-2002','queued','MECH-310','AMR-Beta','Queued for putaway'),
  ('SHP-DEMO-2003','processing','SKU-002','AMR-Alpha','Being verified at receiving'),
  ('SHP-DEMO-2004','completed','SKU-001','AMR-Beta','Putaway completed')
) v(number,status,sku,robot_name,notes)
join users u on u.email='operator@robu.io' left join robots r on r.name=v.robot_name
on conflict (shipment_number) do nothing;

insert into shipment_items (shipment_id, product_id, expected_quantity, crate_label)
select s.id, p.id, v.quantity, 'CRATE-'||right(v.number,4)
from (values ('SHP-DEMO-2001','PACK-402',60),('SHP-DEMO-2002','MECH-310',12),('SHP-DEMO-2003','SKU-002',40),('SHP-DEMO-2004','SKU-001',80)) v(number,sku,quantity)
join incoming_shipments s on s.shipment_number=v.number join products p on p.sku=v.sku
where not exists (select 1 from shipment_items i where i.shipment_id=s.id and i.product_id=p.id);

insert into inventory_events (product_id, inventory_item_id, event_type, quantity_change, robot_id, notes)
select p.id, i.id, v.event_type, v.quantity, r.id, 'Supabase demo telemetry: '||v.note
from (values
  ('SKU-001',80,'putaway','Receiving dock to storage'),('SKU-002',40,'putaway','Receiving dock to storage'),
  ('MECH-101',-20,'pick','Bulk storage to shipping bay'),('MECH-204',-2,'pick','Bulk storage to shipping bay'),
  ('PACK-402',60,'putaway','Receiving dock to shipping supplies'),('SKU-003',-1,'relocation','High velocity cycle count')
) v(sku,quantity,event_type,note)
join products p on p.sku=v.sku join inventory_items i on i.product_id=p.id join robots r on r.name='AMR-Alpha'
where not exists (select 1 from inventory_events e where e.notes='Supabase demo telemetry: '||v.note and e.product_id=p.id);

-- Verification result in the SQL Editor.
select 'users' as table_name, count(*) as rows from users
union all select 'product_categories', count(*) from product_categories
union all select 'products', count(*) from products
union all select 'inventory_items', count(*) from inventory_items
union all select 'inventory_events', count(*) from inventory_events
union all select 'customer_orders', count(*) from customer_orders
union all select 'incoming_shipments', count(*) from incoming_shipments
union all select 'robots', count(*) from robots;
