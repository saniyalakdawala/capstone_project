# EIDT System Setup, Security, and Database Manual

## 1. Quick Start

### Prerequisites
- **Python**: 3.10+ (Tested on Python 3.13)
- **Node.js**: v18+ (Tested on Node v22.18)
- **PostgreSQL**: PostgreSQL 17+ (or PostgreSQL 14+; with SQLite fallback supported for portable runs)
- **PostGIS**: Spatial extension (optional but recommended; automatic Shapely/GeoPandas fallback operates when PostGIS is not yet installed)

---

## 2. Environment & Secrets Security

### A. Environment Files Configuration
1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. For frontend-specific settings, `.env` in the repository root is automatically loaded by Vite (`envDir: '..'`). Only variables prefixed with `VITE_` are exposed to the client bundle.
3. **Strict Git Exclusion**:
   - `.env`, `.env.*`, `frontend/.env`, and `backend/.env` are strictly excluded in `.gitignore`.
   - Never remove `.env` from `.gitignore`.
   - Never commit API keys or database passwords to tracked Git files.

### B. Google Maps Platform API Key Security & Rotation

> [!WARNING]
> If a Google Maps API key was previously committed to version control, it must be rotated immediately in Google Cloud Console. Follow the procedure below.

#### Key Rotation Procedure:
1. **Log in to Google Cloud Console**:
   Navigate to [Google Cloud Credentials](https://console.cloud.google.com/google/maps-apis/credentials).
2. **Create New API Key**:
   - Click **+ CREATE CREDENTIALS** -> **API key**.
   - Assign a descriptive name (e.g. `eidt-frontend-maps-production`).
3. **Configure Required Restrictions (MANDATORY)**:
   - **Application restrictions**: Select **Websites (HTTP referrers)**.
     Add authorized referrers:
     - `http://localhost:5173/*`
     - `http://127.0.0.1:5173/*`
     - Your production domain (e.g., `https://your-domain.gov.in/*`)
   - **API restrictions**: Select **Restrict key**.
     In the dropdown, select **only**:
     - `Maps JavaScript API`
4. **Deploy the New Key**:
   - Update `.env`:
     ```env
     GOOGLE_MAPS_API_KEY=your_new_restricted_key
     VITE_GOOGLE_MAPS_API_KEY=your_new_restricted_key
     ```
   - Alternatively, enter the key directly in the browser UI via the frontend settings dialog (stored only in browser `localStorage`).
5. **Verify and Deprecate the Old Key**:
   - Verify that Google basemaps (Street, Satellite, Terrain) load in the UI.
   - Delete or disable the compromised key in Google Cloud Console.

---

## 3. Database Configuration & Safe Migrations

The platform connects to PostgreSQL using `DATABASE_URL` (configured in `.env`). If PostgreSQL is unavailable, it automatically falls back to the embedded SQLite database (`backend/eidt_mumbai.db`).

### A. Migration Commands

All database schema evolutions are non-destructive and safe to rerun multiple times.

1. **Check Migration Status**:
   ```bash
   cd backend
   python database/migrate.py --status
   ```
   Output:
   ```text
   --- Migration Status (postgresql) ---
     [APPLIED] 001_regional_mmr_foundation
   ```

2. **Execute Pending Migrations**:
   ```bash
   cd backend
   python database/migrate.py
   ```
   This safely adds columns (`parent_region_id`, `region_type`, `hierarchy_path` to `study_areas`; `locality_name`, `sub_ward` to `infrastructure`; `locality_name`, `elevation_m` to `road_segments`), creates new tables (`buildings`, `locality_alerts`, `data_provenance_logs`), and records the migration in `schema_migrations` without deleting or resetting any existing data.

3. **Fresh Database Initialization (Safe)**:
   ```bash
   cd backend
   python database/init_db.py
   ```
   *Note: If the database already exists, `init_db.py` automatically delegates to `migrate.py` to prevent table drops.*

---

## 4. PostGIS 17 Verification & Installation Guide

### Current Verification Status
- **PostgreSQL 17.5**: Operational and connected.
- **PostGIS Extension**: Currently **NOT installed** in the PostgreSQL 17 environment (`pg_available_extensions` does not include PostGIS).
- **Temporary Spatial Fallback**: **ACTIVE AND OPERATIONAL**. The platform utilizes GeoPandas, Shapely 2.0, and GeoJSON bounding box filtering. All spatial queries, routing, and ward exposures function accurately without data loss.

### How to Install PostGIS on Windows PostgreSQL 17

To enable native database spatial operators (`ST_Intersects`, `ST_Buffer`, `GIST` indices):

1. **Using EnterpriseDB Application Stack Builder**:
   - Open Windows Start Menu -> Search for **Application Stack Builder**.
   - Select your PostgreSQL 17 installation (`PostgreSQL 17 on port 5432`).
   - Expand **Spatial Extensions** -> Check **PostGIS 3.5 Bundle for PostgreSQL 17**.
   - Complete the installation wizard (accept default spatial library configurations).

2. **Alternatively (Manual Bundle Archive)**:
   - Download the official PostGIS binary package for PG 17 from [PostGIS Windows Releases](https://postgis.net/windows_downloads/).
   - Extract files into `C:\Program Files\PostgreSQL\17`.

3. **Activate Extension in Database**:
   Once binaries are installed, connect using `psql` or pgAdmin and run:
   ```sql
   \c eidt_mumbai;
   CREATE EXTENSION IF NOT EXISTS postgis;
   ```

4. **Verify Activation**:
   ```bash
   curl http://127.0.0.1:8000/api/health
   ```
   The response will confirm: `"postgis_enabled": true`.

---

## 5. External API Credential Setup

### A. Copernicus Data Space Ecosystem (CDSE)
1. Register at [https://dataspace.copernicus.eu/](https://dataspace.copernicus.eu/).
2. In user settings, generate OAuth2 credentials:
   - `CDSE_CLIENT_ID`
   - `CDSE_CLIENT_SECRET`

### B. NASA Earthdata Login (GPM IMERG)
1. Register at [https://urs.earthdata.nasa.gov/](https://urs.earthdata.nasa.gov/).
2. Authorize **GES DISC** for GPM precipitation products.
3. Add `EARTHDATA_USERNAME` and `EARTHDATA_PASSWORD` to `.env`.

### C. India Meteorological Department (IMD)
1. API access via Ministry of Earth Sciences at [https://mausam.imd.gov.in/](https://mausam.imd.gov.in/).
2. When unset, EIDT automatically uses benchmark IMD Santacruz (43003) and Colaba (43057) observations.

---

---

## 7. Phase 4 — Emergency Routing, Shelters & Evacuation Decision Support

### A. Road Network Architecture
The EIDT platform utilizes a topologically connected directed routing graph constructed directly from **6,778 real OpenStreetMap road segments** in the Mumbai Metropolitan Region (MMR):
- **Graph Nodes**: 8,072 snapped coordinate junctions (precision $1.1\times 10^{-5}$ deg / ~1.1m tolerance).
- **Directed Edges**: 17,890 directed links preserving one-way restrictions, empirical free-flow speed limits, and length metrics.
- **Topological Connectivity**: 99.6% single giant connected component.
- **Attribution**: © OpenStreetMap contributors under the Open Database License (ODbL).

### B. Verified Emergency Facilities & Shelters
- **45 Verified Facilities Ingested**:
  - **26 Emergency Hospitals & Trauma Centers**: Including KEM, Sion LTMGH, Nair, Lilavati, and Asian Heart Institute.
  - **13 Designated Evacuation Shelters**: Officially verified civic relief centres and municipal school relief shelters (e.g. Kurla Municipal Urdu/Marathi Schools, Dharavi Transit Camp civic relief points).
  - **3 Fire & Rescue Stations**: BKC, Chembur, and Dharavi stations.
  - **3 Police Stations**: Kurla, Bandra-Kurla Complex, and Dharavi police stations.
- **Capacity Transparency**: Shelters carry designated capacities only where officially verified; hospitals and public buildings are strictly distinguished from shelters.

### C. Hazard-Aware Routing Engine
The routing service combines Dijkstra shortest distance, fastest travel time, and dynamic hazard weighting:
- **Active Road Closure Avoidance**: Closed corridors (e.g., Andheri Subway underpass, flooded lowlands) are completely blocked from pathfinding.
- **Flood Penalization**: Integrates dynamic 24-hour flood hazard output from Phase 2/3, multiplying travel cost on waterlogged links.
- **Alternative Corridor Generation**: Implements Yen's algorithm to compute secondary independent evacuation corridors.
- **Nearest Reachable Facility**: Computes the optimal accessible hospital or shelter based on real road travel time.
- **Safety Transparency (Mandatory Rule 6)**: Every route response includes explicit uncertainty disclaimers and safety notices stating that no route is guaranteed safe.

### D. Hypothetical Scenario Isolation
Users can simulate custom road closures and hazard conditions via `/api/evacuation/scenarios`. Hypothetical restrictions are strictly isolated with `is_hypothetical_scenario=True` and do not alter real-time operational feeds.

### E. Steps for Expanding from MMR to Maharashtra
1. Ingest district-level OSM road networks (e.g. Konkan, Pune, Nashik, Nagpur, Chhatrapati Sambhajinagar) via the documented road ingestion pipeline.
2. Ingest district disaster management authority (DDMA) emergency facility records into `emergency_facilities`.
3. Ingest state traffic police and PWD road blockage notifications into `road_restrictions`.
4. Trigger graph rebuild via `POST /api/routing/network/reload`.

---

## 8. Running Backend, Frontend & Tests

### Starting the Backend:
```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
- Interactive API Swagger docs: `http://127.0.0.1:8000/docs`
- Redoc documentation: `http://127.0.0.1:8000/redoc`

### Starting the Frontend:
```bash
cd frontend
npm run dev
```
Open `http://localhost:5173/` in your browser.

### Building Frontend for Production:
```bash
cd frontend
npm run build
```

### Running Test Suite:
```bash
cd backend
python -m pytest -v
```
All **116 automated tests** across all modules (Phase 1, 2A, 2B, 2C, 3, and 4) will pass without error.

