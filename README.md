# Earth Intelligence Digital Twin (EIDT) — Mumbai Flood Intelligence

> A full-stack, AI-powered regional geospatial digital twin that models urban flood risk, simulates extreme rainfall scenarios, and analyzes infrastructure connectivity in Mumbai, Maharashtra, India.

---

## Architecture Overview

```
                      +---------------------------------------+
                      |       Multi-Source Data Ingestion     |
                      |  - Copernicus Sentinel-1/2 (CDSE)     |
                      |  - NASA GPM IMERG Precipitation       |
                      |  - Copernicus GLO-30 DEM              |
                      |  - OpenStreetMap Vector Overpass      |
                      |  - WorldPop 100m Demographic Grid     |
                      |  - Dartmouth Flood Observatory Archive|
                      |  - IMD Santacruz & Colaba AWS         |
                      |  - ArcGIS Living Atlas Feature Layer  |
                      +-------------------+-------------------+
                                          |
                                          v
+---------------------------------------------------------------------------------+
|                         PostgreSQL / PostGIS Database                           |
|  - StudyArea (Wards)            - EnvironmentalFeatures (Rivers, DEM)          |
|  - WeatherObservations          - Infrastructure (Hospitals, Schools)          |
|  - SatelliteObservations        - RoadSegments (Network Topology)              |
|  - FloodEvents (Ground Truth)   - Scenarios & SimulationResults                |
+-----------------------------------------+---------------------------------------+
                                          |
                                          v
+---------------------------------------------------------------------------------+
|                       AI & Hydrological Simulation Engines                      |
|  - Model A: SAR Satellite Flood Mapping & Inundation Extraction                 |
|  - Model B: Random Forest Classifier (ROC-AUC 0.914 vs Logistic Reg 0.761)      |
|  - Model C: NetworkX Dijkstra Topological Emergency Routing & Facility Cut-off  |
|  - Model D: SCS-CN Overland Runoff & Tidal Lock Scenario Simulation Engine      |
+-----------------------------------------+---------------------------------------+
                                          |
                                          v
+---------------------------------------------------------------------------------+
|                               FastAPI REST Backend                              |
|  - /api/health                          - /api/analytics/exposure               |
|  - /api/study-areas                     - /api/analytics/accessibility          |
|  - /api/weather                         - /api/models/metrics                   |
|  - /api/infrastructure                  - /api/data-pipeline/status             |
|  - /api/scenarios                       - /api/data-pipeline/trigger            |
+-----------------------------------------+---------------------------------------+
                                          |
                                          v
+---------------------------------------------------------------------------------+
|                         React + TypeScript Vite Frontend                        |
|  - Warm Beige & Sage Editorial Aesthetic (DM Serif Display + Inter)             |
|  - Interactive Multi-Layer Leaflet Map (Carto Light Basemap)                    |
|  - Real-Time Flood Scenario Simulator & Mitigation Controls                     |
|  - Hospital Emergency Route Navigator with Flood Closures                       |
|  - WorldPop 100m Population Exposure Visualizer                                 |
|  - Historical Deluge Archive (2005, 2017, 2019)                                 |
|  - Academic Model Insights (RQ1, RQ2, RQ3, Feature Importance, Confusion Matrix)|
|  - Automated Data Pipeline & Provenance Registry Panel                          |
+---------------------------------------------------------------------------------+
```

---

## How to Run

### Option A: Both Servers Are Already Running Live!
The development processes are currently running in the background:
- **Frontend Dashboard**: [http://127.0.0.1:5173/](http://127.0.0.1:5173/)
- **FastAPI Backend**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Interactive Swagger API Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

### Option B: Running Manually from Terminals

#### 1. Backend Server
```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

#### 2. Frontend Application
```bash
cd frontend
npm run dev
```
Open [http://localhost:5173/](http://localhost:5173/) in your web browser.

#### 3. Database Initialization & Seeding (if needed)
```bash
python backend/database/init_db.py
python backend/database/seed_data.py
```

#### 4. Automated Tests
```bash
# Run all tests (API & OSM real-data integration):
python -m pytest backend/tests/ -v

# Run specifically the OpenStreetMap real data pipeline integration test:
python -m pytest backend/tests/test_osm_integration.py -v
```

#### 5. OpenStreetMap Real-Data Ingestion Pipeline
```bash
# Execute the repeatable, idempotent OpenStreetMap real-data ingestion pipeline:
python backend/app/ingestion/osm_pipeline.py
```
This script:
1. Downloads real raw OSM XML for the Mumbai pilot study area (`[72.860, 19.055, 72.885, 19.075]`) into `backend/data/raw/openstreetmap/`.
2. Parses topological road networks using OSMnx 2.1, validating geometries and CRS to `EPSG:4326`.
3. Extracts real hospitals, schools, and Mithi River waterways.
4. Exports processed vector layers to `backend/data/processed/openstreetmap/` as GeoJSON and multi-layer GeoPackage (`mumbai_osm.gpkg`).
5. Performs an idempotent batch upsert into PostgreSQL/PostGIS (`road_segments` and `infrastructure` tables), checking primary keys to prevent duplication.

#### 6. Automated Multi-Source Pipeline Runner
```bash
# Run all environmental connectors:
python -c "import sys; sys.path.insert(0, 'backend'); from app.ingestion.pipeline_runner import pipeline_runner; print(pipeline_runner.run_all())"
```

---

## Deliverables Index

- [docs/DATA_SOURCE_REGISTRY.md](file:///c:/Projects/capstone_project/docs/DATA_SOURCE_REGISTRY.md): Comprehensive documentation of all 8 public data sources, licenses, spatial/temporal resolutions, and endpoints.
- [docs/SETUP_GUIDE.md](file:///c:/Projects/capstone_project/docs/SETUP_GUIDE.md): Step-by-step credentials and API onboarding instructions.
- [docs/RESEARCH_REPORT.md](file:///c:/Projects/capstone_project/docs/RESEARCH_REPORT.md): Academic defense addressing Research Questions 1, 2, and 3.
- [docs/DATABASE_MANUAL.md](file:///c:/Projects/capstone_project/docs/DATABASE_MANUAL.md): Schema architecture, spatial indices, relational normalization, and sample GIS-aware SQL queries.
- [.env.example](file:///c:/Projects/capstone_project/.env.example): Environment variable credentials template.
