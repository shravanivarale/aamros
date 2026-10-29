# Robu — Autonomous Inventory Management Platform

An enterprise-grade orchestration platform for autonomous warehouse robotics, integrating with ROS2 for navigation, ArUco detection, and inventory operations.

## Architecture

- **Backend** — FastAPI orchestration layer (auth, inventory, task scheduling, WebSocket gateway, ROS2 bridge)
- **Frontend** — React/TypeScript with three portals (Customer, Warehouse Intake, Robotics Command)
- **Database** — PostgreSQL with SQLAlchemy ORM
- **Cache** — Redis for async task coordination
- **Robotics** — High-level task interface to existing ROS2 system (no low-level motor control)

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 20+
- Python 3.12+ (for local backend development)

### 1. Start infrastructure

```bash
docker compose up -d postgres redis
```

### 2. Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
python -m scripts.seed
uvicorn app.main:app --reload --port 8000
```

To populate the full demo warehouse workflow, run `python scripts/seed_demo.py` from `backend`. The seeder is idempotent and works with SQLite or Supabase. For Supabase, copy the exact **Transaction pooler** connection string from Supabase Dashboard > Connect into `backend/.env` as `SUPABASE_DATABASE_URL` first, then run the same command. The direct `db.<project-ref>.supabase.co` host is not reachable in some Windows networks; do not use the placeholder URL from `.env.example`.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5174

## Production Deployment

Deploy the frontend and backend as separate services:

1. **Railway backend:** create a Railway project from this repository and set the service root directory to `backend`. Add a PostgreSQL
	service, generate a public domain, and configure `ENVIRONMENT=production`, `DATABASE_URL=${{Postgres.DATABASE_URL}}`, a generated
	`SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, and `CORS_ORIGINS` set to the exact Vercel origin. Add `GROQ_API_KEY`,
	`FIREBASE_PROJECT_ID`, and robot bridge variables only when those features are used. Keep one replica. See [RAILWAY.md](RAILWAY.md).
2. **Vercel frontend:** create a Vercel project from the same repository. Either set the root directory to `frontend` or leave the root at
	the repository root; both configurations are included. Set the build-time variable `VITE_API_BASE_URL` to the Railway public URL,
	without a trailing slash, then redeploy.
3. **Verify:** open `https://<railway-domain>/health`, then log in through the Vercel URL. Browser requests should use the Railway URL and
	the live connection should use `wss://<railway-domain>/ws`.

Never put backend secrets such as `SECRET_KEY`, database URLs, or `GROQ_API_KEY` in Vercel variables or frontend files. Rotate any
credentials that have been exposed outside the secret manager.

### Demo Accounts

| Role       | Email               | Password      |
|------------|---------------------|---------------|
| Admin      | admin@robu.io       | admin12345    |
| Operator   | operator@robu.io    | operator123   |
| Customer   | customer@robu.io    | customer123   |

## API Documentation

When running in development mode, visit http://localhost:8000/docs for the interactive OpenAPI documentation.

## Project Structure

```
robu/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # REST API routers
│   │   ├── core/            # Config, security, enums, deps
│   │   ├── db/              # Database session & base models
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   ├── services/        # Business logic layer
│   │   ├── repositories/    # Data access layer
│   │   ├── ros2_bridge/     # ROS2 integration interface
│   │   ├── websocket/       # Real-time event gateway
│   │   └── main.py          # Application entry point
│   ├── alembic/             # Database migrations
│   └── scripts/             # Seed & utility scripts
├── frontend/
│   └── src/
│       ├── api/             # API client
│       ├── components/      # Reusable UI components
│       ├── hooks/           # Custom React hooks
│       ├── pages/           # Portal pages
│       ├── stores/          # Zustand state management
│       └── types/           # TypeScript interfaces
└── docker-compose.yml
```

## Three Portals

1. **Customer Portal** — Browse products, place orders, track robot execution
2. **Warehouse Intake** — Register incoming shipments for autonomous robot processing
3. **Robotics Command** — Fleet monitoring, inventory management, analytics dashboard

## Development Roadmap

See `agileMethodology.md` for the full sprint plan. Current status: **Sprint 1** (Foundation) complete.
