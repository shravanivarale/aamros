# Robot integration (ArmsBot, ROS 2) — how the live data flows

```
 board (UNO Q) ── TCP ──> ROS 2 stack (arms_ws) ──> wms_bridge :8005 ── HTTP ──> backend :8000 ── WebSocket /ws ──> frontend
                          odom, LiDAR, AMCL,         real pose, status,           robot_sync: DB + WS broadcast
                          A* + waypoint_nav          events, map, camera,         task_dispatch: orders/shipments -> robot
                                                     task execution               task_sync: task -> order/shipment/stock
```

Nothing is simulated: values the robot does not measure are `null` / `-1` and shown as "n/a" (e.g. battery, there is no battery sensor).

## Run it

1. **Robot PC** (the one in `arms_ws`), after the map exists in `~/maps`:
   ```bash
   source /opt/ros/humble/setup.bash && source ~/Downloads/arms_ws/install/setup.bash
   # telemetry only (robot never moves from WMS commands):
   ros2 launch armsbot_nav wms.launch.py map:=$HOME/maps/<map>.yaml host:=10.113.140.10 camera:=true
   # also execute WMS tasks / manual jog (the robot drives!):
   ros2 launch armsbot_nav wms.launch.py map:=$HOME/maps/<map>.yaml host:=10.113.140.10 allow_motion:=true
   ```
   `start_at_home:=true` assumes the robot starts on the taught `HOME` location and tells AMCL. Otherwise set the robot's pose from the
   map page ("Robot is here"). Tasks only run while the robot is localized.
2. **Backend**: `uvicorn app.main:app --port 8000`. A fresh install seeds its first robot PC from `ROS_BRIDGE_URL` (default
   `http://10.113.140.148:8005`); after that the list is managed in the dashboard.
   **Robot PCs are added in the dashboard**: Settings → *Robot bridges* (admin only). Enter the IP/hostname and port (8005), press
   *Test connection* (shows the robots it reports and whether motion is enabled), then *Add*. Several robot PCs can be listed; each is polled
   independently, can be disabled or removed without a restart, and an unreachable one only marks its own robots offline.
   The robot PC must allow inbound TCP 8005 (the bridge listens on 0.0.0.0).
   For anything beyond a trusted LAN (e.g. a cloud backend) start the bridge with `api_token:=<secret>` and enter the same token (and `https`
   for a tunnel) when adding it; see `RAILWAY.md`.
3. **Frontend**: `npm run dev`, log in as an admin/operator.
4. **Teach locations** (Warehouse Map → Locations): press-drag on the map for position + heading, name it, save. Needed: at least one
   `rack_slot`, one `receiving`, one `shipping` (and `home`). The robot rejects spots on walls / unmapped space / < 0.30 m from a wall.

## What happens when…

| Event | Result |
|---|---|
| Robot bridge starts | robot registers itself, appears on the dashboards, the active map is copied into the backend, locations are pushed |
| Customer places an order | one task per product → dispatched to a free, localized robot → drives to the product's rack location, then to `shipping` → order `delivered`, stock deducted once, `inventory_events` row written |
| Operator registers a shipment | one task per crate → robot drives `receiving` → rack slot → shipment `completed`, stock added once |
| Task has no location yet | stays queued with the reason on the task; starts by itself once the location is taught |
| A robot PC is unreachable | only its robots are shown `offline`, tasks for them return 503 (never "accepted"), others keep working, recovers automatically |

**Navigation only:** ArmsBot has no lift/gripper, so "pick" and "place" are arrivals (`physical_handling: false` in the events). The
backend still updates stock when the task completes (the original behaviour), so stock can diverge from the real shelves.

## Tests (no robot needed)
```bash
python3 tools/test_wms_bridge_sim.py   --map <sim ring map>.yaml                         # bridge + simulator
python3 tools/test_wms_backend_sim.py  --map <sim ring map>.yaml --backend-python <venv>/bin/python   # + backend, orders, shipments, WebSocket
```
