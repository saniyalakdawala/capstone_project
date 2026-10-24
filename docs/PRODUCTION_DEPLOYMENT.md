# Earth Intelligence Digital Twin (EIDT) — Maharashtra
## Production Deployment Architecture & Specification (Phase 7)

### 1. Architectural Topology

The EIDT Maharashtra platform employs a micro-service and layered container topology designed for high-availability geospatial workloads:

```
[ Internet / Clients ]
         │
         ▼
[ Nginx Reverse Proxy (Port 80/443) ]
  ├── Gzip Compression (Level 6)
  ├── Security Headers (CSP, HSTS, X-Frame-Options)
  ├── Static Bundle Cache (30-day immutable)
  │
  ├──► / (SPA Frontend: React 18 + Leaflet + Vite Build)
  │
  └──► /api/ (Reverse Proxied to FastAPI Backend Container)
         │
         ▼
[ FastAPI Geospatial Backend (Port 8000, 4 Uvicorn Workers) ]
  ├── ObservabilityMiddleware (X-Correlation-ID & API Metric Logging)
  ├── Multi-Scale Douglas-Peucker Simplification (Dynamic Zoom Lod)
  ├── Viewport Bounding-Box Spatial Filters
  ├── Shapely 2.0 / GeoPandas Fallback Geospatial Engine
  │
  ├──► [ PostgreSQL 16 + PostGIS 3.4 Spatial Database (Port 5432) ]
  │      ├── Composite B-Tree Indexes on Hierarchy, Temporal, and Infrastructure
  │      ├── Schema Migrations Ledger (Migrations 001 - 008)
  │      └── Connection Pool: 20 max overflow, 10 base connections
  │
  └──► [ Background Scheduler Worker (APScheduler) ]
         ├── IMD AWS Weather Ingestion (Every 15 mins)
         ├── GPM IMERG Satellite Precipitation (Every 30 mins)
         ├── Regional Tiled Ingestion Engine (0.25° Spatial Bins)
         └── Alert Lifecycle State Machine (State Transitions & Notifications)
```

---

### 2. Service Definitions & Ports

| Service Name | Container Name | Base Image | Port | Description |
|---|---|---|---|---|
| **db** | `eidt_postgres` | `postgis/postgis:16-3.4-alpine` | `5432` | Primary relational and spatial database with PostGIS 3.4 extension. |
| **backend** | `eidt_backend` | `python:3.11-slim-bullseye` | `8000` | REST API service running 4 Uvicorn workers behind Gunicorn. |
| **scheduler** | `eidt_scheduler` | `python:3.11-slim-bullseye` | N/A | Worker process executing scheduled ingestion, monitoring, and alerts. |
| **frontend** | `eidt_frontend` | `nginx:1.25-alpine` | `80` | Production web server hosting Vite bundle and routing `/api/` traffic. |

---

### 3. Environment Configurations

| Environment Variable | Allowed Values | Default | Purpose |
|---|---|---|---|
| `ENVIRONMENT` | `development`, `staging`, `production` | `production` | Controls logging verbosity and error display. |
| `POSTGRES_USER` | alphanumeric | `postgres` | Database admin user. |
| `POSTGRES_PASSWORD` | string | `postgres` | Database password. |
| `POSTGRES_DB` | string | `eidt_mumbai` | Database schema name. |
| `DATABASE_URL` | URI string | `postgresql://...` | Full connection URI. |
| `CORS_ORIGINS` | comma-separated URLs | `http://localhost,http://localhost:80` | Whitelisted cross-origin request sources. |
| `ALLOW_DEMO_FALLBACK` | `true`, `false` | `true` | Allows synthetic testing fixtures when external feeds are down. |
| `REQUEST_TIMEOUT_SECONDS` | integer | `25` | Network timeout for outbound API connectors. |

---

### 4. Step-by-Step Deployment Guide

#### 4.1 Prerequisites
- Docker Engine 24.0+ and Docker Compose v2.20+
- Minimum 4 GB RAM and 2 vCPUs
- 20 GB free disk space (for satellite rasters and elevation DEM tiles)

#### 4.2 Configuration
```bash
# 1. Clone repository
git clone https://github.com/your-org/capstone_project.git
cd capstone_project

# 2. Configure production environment
cp .env.example .env
# Edit .env with production credentials:
# nano .env
```

#### 4.3 Container Orchestration
```bash
# 3. Build and launch services in detached mode
docker compose up -d --build

# 4. Verify running health checks
docker compose ps

# Expected output:
# NAME             STATUS                   PORTS
# eidt_postgres    Up (healthy)             0.0.0.0:5432->5432/tcp
# eidt_backend     Up (healthy)             0.0.0.0:8000->8000/tcp
# eidt_scheduler   Up (healthy)             
# eidt_frontend    Up (healthy)             0.0.0.0:80->80/tcp
```

#### 4.4 Database Initialization & Seeding
```bash
# 5. Run database migrations inside the backend container
docker compose exec backend python database/migrate.py

# 6. Seed Maharashtra State, Divisions, and 36 Districts
docker compose exec backend python -c "from app.database import SessionLocal; from app.services.geo_hierarchy import seed_maharashtra_hierarchy; db=SessionLocal(); print(seed_maharashtra_hierarchy(db))"
```

---

### 5. Health Probes Specification

The platform exposes three distinct health probe endpoints adhering to Kubernetes / Docker best practices:

1. **Liveness Probe**: `GET /api/health/live`
   - Returns: HTTP 200 `{ "status": "ok", "uptime_seconds": ..., "process_id": ... }`
   - Purpose: Verifies whether the FastAPI event loop is active and processing requests.
2. **Readiness Probe**: `GET /api/health/ready`
   - Returns: HTTP 200 if PostgreSQL connection latency is healthy, HTTP 503 if database is disconnected.
   - Purpose: Directs traffic only when backend dependencies are connected.
3. **Data Readiness Probe**: `GET /api/health/data-readiness`
   - Returns: HTTP 200 `{ "status": "current" | "stale", "observation_count_24h": ..., "study_areas_verified": 53, "known_limitations": [...] }`
   - Purpose: **Prevents false all-clears**. A healthy process does not imply fresh hazard data.
