# EIDT System Setup and Data Connector Guide

## 1. Quick Start

### Prerequisites
- **Python**: 3.10+ (Tested on Python 3.13)
- **Node.js**: v18+ (Tested on Node v22.18)
- **PostgreSQL**: PostgreSQL 14+ with PostGIS extension (or standard PostgreSQL with fallback JSON/WKT geometries)

### Environment Configuration
1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. The application is configured to run out-of-the-box with active open APIs (OpenStreetMap Overpass, NASA POWER Precipitation, Open-Elevation) and verified benchmark datasets.

---

## 2. External API Credential Setup

### A. Copernicus Data Space Ecosystem (CDSE)
1. Navigate to [https://dataspace.copernicus.eu/](https://dataspace.copernicus.eu/) and create an account.
2. In your user settings, generate OAuth2 API credentials:
   - `CDSE_CLIENT_ID`
   - `CDSE_CLIENT_SECRET`
3. Add these credentials to your `.env` file to enable automated raw Sentinel-1 GRD and Sentinel-2 L2A tile downloads.

### B. NASA Earthdata Login
1. Register for a free NASA Earthdata account at [https://urs.earthdata.nasa.gov/](https://urs.earthdata.nasa.gov/).
2. In your profile applications, authorize **GES DISC** for GPM precipitation products.
3. Add to `.env`:
   ```env
   EARTHDATA_USERNAME=your_username
   EARTHDATA_PASSWORD=your_password
   ```

### C. India Meteorological Department (IMD)
1. For official real-time automated weather station telemetry, submit an API onboarding request to the Ministry of Earth Sciences at [https://mausam.imd.gov.in/](https://mausam.imd.gov.in/).
2. Configure `IMD_API_KEY` in `.env`.
3. When unset, EIDT automatically reports `CONFIGURED_WITH_IMD_BENCHMARKS` using verified IMD Santacruz (43003) and Colaba (43057) observations.

### D. Esri ArcGIS Maps SDK & Living Atlas
1. Register at [https://developers.arcgis.com/](https://developers.arcgis.com/).
2. Create an API Key with `Basemaps` and `Living Atlas` privileges.
3. Configure `ARCGIS_API_KEY` in `.env`.

---

## 3. Running the Data Pipeline

### Via Command-Line
Run all 8 connectors and update local provenance:
```bash
python -c "from app.ingestion.pipeline_runner import pipeline_runner; print(pipeline_runner.run_all())"
```

Run a specific connector (e.g. OpenStreetMap):
```bash
python -c "from app.ingestion.pipeline_runner import pipeline_runner; print(pipeline_runner.run_connector('openstreetmap'))"
```

### Via REST API
- Check real-time connector status:
  `GET http://127.0.0.1:8000/api/data-pipeline/status`
- View full dataset registry:
  `GET http://127.0.0.1:8000/api/data-pipeline/registry`
- Trigger on-demand pipeline ingestion:
  `POST http://127.0.0.1:8000/api/data-pipeline/trigger?source_id=openstreetmap`

---

## 4. Running Backend and Frontend

### Starting the Backend:
```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Interactive API documentation available at: `http://127.0.0.1:8000/docs`

### Starting the Frontend:
```bash
cd frontend
npm run dev
```
Open `http://localhost:5173/` in your browser.
