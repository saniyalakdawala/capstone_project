# Earth Intelligence Digital Twin (EIDT) — Maharashtra
## Operator Runbook & Incident Management Guide (Phase 7)

### 1. Daily Operator Workflows

#### 1.1 Local Development Startup (Windows / Linux)
```powershell
# In PowerShell:
$env:PYTHONPATH="backend"
$env:ALLOW_DEMO_FALLBACK="true"

# Run database migrations:
C:\Python313\python.exe backend/database/migrate.py

# Launch FastAPI backend:
C:\Python313\python.exe -m uvicorn app.main:app --app-dir backend --reload --port 8000

# In a separate terminal, launch frontend development server:
cd frontend
npm run dev
```

---

### 2. Regional Data Ingestion & District Onboarding

#### 2.1 Onboarding a New Maharashtra District
To onboard a district outside the Mumbai pilot corridor:

1. **Verify District Hierarchy**: Confirm the district ID exists in `backend/app/services/geo_hierarchy.py` (e.g., `DIST_PUNE`, `DIST_NAGPUR`, `DIST_RATNAGIRI`).
2. **Generate Spatial Ingestion Tiles**:
   ```bash
   # Decompose the district bounding box into 0.25° spatial tiles
   curl -X POST "http://localhost:8000/api/regional-ingestion/generate-tiles?district_id=DIST_PUNE&tile_size_deg=0.25"
   ```
3. **Trigger Tile Ingestion Batch**:
   ```bash
   # Ingest a specific tile
   curl -X POST "http://localhost:8000/api/regional-ingestion/ingest-tile?tile_id=TILE_DIST_PUNE_1852_7385&source_type=WEATHER_IMD"
   ```
4. **Audit Statewide Coverage Gaps**:
   ```bash
   curl -s "http://localhost:8000/api/regional-ingestion/summary" | jq .coverage_gaps
   ```

---

### 3. Source Disabling & Incident Response

#### 3.1 Disabling an Unhealthy or Failing Data Source
If an external API (e.g., OpenTopography, IMD AWS, CDSE) undergoes downtime, degradation, or returns malformed payloads:

1. Inspect source health status:
   ```bash
   curl -s "http://localhost:8000/api/monitoring/sources/health"
   ```
2. Manually override or pause ingestion in `backend/app/services/scheduler_service.py` by pausing the scheduled job:
   ```python
   # In Python session:
   from app.services.scheduler_service import get_orchestration_scheduler
   scheduler = get_orchestration_scheduler()
   scheduler.scheduler.pause_job("fetch_imd_aws_observations")
   ```
3. The platform automatically falls back to last-known verified observations and marks data freshness as degraded in `GET /api/health/data-readiness`.

#### 3.2 Identifying Stale Hazard Layers
To verify if hazard predictions are out of date:
1. Query `GET /api/health/data-readiness`:
   ```bash
   curl -s "http://localhost:8000/api/health/data-readiness"
   ```
2. If `status` returns `"stale"`, check the `data_freshness_timestamp`.
3. If the timestamp exceeds 48 hours, hazard layers display a prominent "Data Stale - Offline Reanalysis" banner on the frontend map.

---

### 4. Backup & Disaster Recovery Procedures

#### 4.1 Running Scheduled Backups
```bash
# Execute automated backup (creates compressed .sql.gz and SHA-256 metadata)
C:\Python313\python.exe scripts/backup_db.py

# Backups are stored in /backups/ with metadata:
#   backups/eidt_backup_YYYYMMDD_HHMMSS.sql.gz
#   backups/eidt_backup_YYYYMMDD_HHMMSS_meta.json
```

#### 4.2 Executing Isolated Disaster Recovery Test
```bash
# Tests the latest backup against an isolated temporary database
# Verifies record counts, migration ledgers, and cleans up automatically:
C:\Python313\python.exe scripts/restore_db.py
```

---

### 5. Security & Secret Rotation Protocol

#### 5.1 Scanning for Committed Secrets
```bash
# Runs the automated regex scanner on tracked Git repository files:
C:\Python313\python.exe scripts/security_audit.py
```

#### 5.2 Rotating Google Maps / API Credentials
1. In Google Cloud Console:
   - Create new Maps JavaScript API key.
   - Configure HTTP referrer restriction: `https://your-domain.gov.in/*`.
   - Restrict API scope strictly to "Maps JavaScript API".
2. Update `.env` file on deployment host:
   ```env
   GOOGLE_MAPS_API_KEY=AIzaSy...
   VITE_GOOGLE_MAPS_API_KEY=AIzaSy...
   ```
3. Rebuild frontend bundle:
   ```bash
   cd frontend && npm run build
   ```
4. Revoke the previous key in Google Cloud Console.

---

### 6. Known Model & Geographic Limitations

1. **Topography (Copernicus 30m DEM)**: Terrain elevation models for Western Ghats (Sahyadri corridor) have 30-meter cell resolution. Micro-drainage channels (<5m width) require local survey data.
2. **Road Network Graph**: High-resolution topological graph routing with dynamic flood speed reduction is operational for the Mumbai Metropolitan Region (MMR). Outside MMR, emergency routing defaults to National/State Highway corridors until taluka road layers are ingested.
3. **Hazard Predictions**: Flash flood and inundation simulations represent hydrological physics-informed estimates; they are intended for emergency decision-support and must be verified against field ground truth during catastrophic events.
