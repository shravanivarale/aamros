# Deploying the backend on Railway

The backend must run as ONE long-lived process (it holds the WebSockets and the robot-sync loop), which is why it cannot stay on
Vercel serverless. Railway runs it from `backend/Dockerfile` (`backend/railway.json` sets the health check and 1 replica).

## 0. The one thing to understand first: Railway cannot reach your robot's LAN address

`10.113.140.148` is a private address. Railway's servers can't connect to it, so adding it to **Settings → Robot bridges** from a cloud backend
will always show *offline*. The robot PC must be reachable from the internet. Recommended: a **Cloudflare Tunnel** (outbound-only, https, free):

```bash
# on the robot PC (10.113.140.148)
ros2 launch armsbot_nav wms.launch.py map:=$HOME/maps/<map>.yaml host:=10.113.140.10 camera:=true \
     api_token:=<a long random secret>            # REQUIRED when the bridge is reachable from the internet
cloudflared tunnel --url http://localhost:8005       # prints https://<random>.trycloudflare.com
```
A quick tunnel gets a new URL each time it restarts; for a stable address create a named tunnel on a domain you own (Cloudflare account).
Without `api_token` anyone who finds the URL could command the robot, so the bridge warns loudly at start-up if it is unset.
(If you would rather not expose the robot at all, run the backend on the robot's LAN instead of Railway.)

## 1. Railway project
1. New Project → **Deploy from GitHub repo** → this repo. In the service **Settings → Root Directory** = `backend`.
2. **Add → Database → PostgreSQL** in the same project.
3. Backend service → **Variables**:

| Variable | Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (Railway reference; the private network is used, no TLS needed) |
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | your first administrator (only used while the users table is empty) |
| `CORS_ORIGINS` | your frontend origin, e.g. `https://your-app.vercel.app` (no trailing slash) |
| `ROS_BRIDGE_URL`, `ROS_BRIDGE_TOKEN` | the tunnel URL and the `api_token` from step 0 (seeds the first robot PC; more are added in the dashboard) |
| `GROQ_API_KEY`, `FIREBASE_PROJECT_ID` | only if you use the assistant / Firebase login |

4. **Settings → Networking → Generate Domain**. Check `https://<domain>/health` returns `{"status":"healthy"}`.
5. Keep **replicas = 1**.

The app refuses to start in production if `SECRET_KEY` is the default or short, if no `DATABASE_URL` is set (it would silently use a SQLite
file that Railway erases on every deploy), or if demo seeding is on. No demo accounts exist in production.

## 2. Frontend
Build the frontend with `VITE_API_BASE_URL=https://<your-railway-domain>` (Vercel → Project → Environment Variables → redeploy). REST calls,
the WebSocket (`wss://`) and the camera feed all use that origin. Add the frontend's URL to `CORS_ORIGINS`.

## 3. Connect the robot
Log in as the admin → **Settings → Robot bridges** (or rely on the seeded one) → address = the tunnel host (https, port 443) and the API token →
*Test connection* shows the robots it reports → *Add*. Then teach locations on the Warehouse Map.

## Checks and limits
- `python tools/test_backend_production_pg.py` (needs `pip install pgserver`) exercises the production start-up on a real PostgreSQL.
- Camera: the browser's `<img>` stream goes through the backend (token in the query string), which adds the bridge token itself.
- One map: the dashboards show the map of the first online robot PC; all PCs should use the same map.
- Robot motion stays OFF (`allow_motion:=false`) until you start the bridge with `allow_motion:=true`.
