# EIDT Geospatial Data Source Registry

## Overview

The **Earth Intelligence Digital Twin (EIDT)** integrates environmental observations, remote sensing imagery, hydrological indices, transport graphs, and demographic distributions for the Mumbai Metropolitan Region (MMR).

To ensure transparency, scientific defensibility, and compliance with the "no fabricated live data" mandate, this registry documents each integrated data source, access mechanisms, licensing, spatial and temporal resolution, and fallback behavior.

---

## Registered Data Sources

| Source ID | Dataset Name | Provider | License | Spatial Resolution | Temporal Revisit | Auth Type | Status |
|-----------|--------------|----------|---------|-------------------|------------------|-----------|--------|
| `copernicus_sentinel1` | Sentinel-1 C-SAR GRD | ESA / Copernicus CDSE | CC-BY-SA 3.0 IGO / Open | 10 meters | 6-12 days | OAuth2 Bearer (CDSE) | Operational / Cache Fallback |
| `copernicus_sentinel2` | Sentinel-2 MSI BOA | ESA / Copernicus CDSE | Copernicus Open Access | 10-20 meters | 5 days | OAuth2 Bearer (CDSE) | Operational / Cache Fallback |
| `nasa_gpm_imerg` | NASA GPM IMERG Final Run | NASA GSFC / GES DISC | NASA Open Data Policy | 0.1° (~10 km) | Half-hourly / Daily | NASA Earthdata / POWER | Live Active |
| `copernicus_dem` | Copernicus DEM GLO-30 | ESA / Airbus | Open WorldDEM-30 | 30 meters (1") | Static (2024 release) | Open REST / OpenTopo | Live Active |
| `openstreetmap` | OSM Transport & Facilities | OpenStreetMap Contributors | ODbL 1.0 | Sub-meter Vector | Continuous Community | Open (Overpass API) | Live Active |
| `worldpop_india` | WorldPop 100m Population | WorldPop / Southampton | CC-BY 4.0 | 100 meters (3") | Annual / 2025 Proj. | Open REST | Live Active |
| `global_flood_db` | DFO & Global Flood Database | Dartmouth Flood Obs. | CC-BY 4.0 | 250m - 10m | Historic Archive | Open Archive | Live Active |
| `imd_aws` | IMD Automatic Weather Stations | India Met Department / MoES | NDSAP Open Govt Data | Point (~15 km radius) | Hourly / 24h Gauge | MoES Registered API | Benchmark Mode |
| `arcgis_living_atlas` | ArcGIS Living Atlas Layers | Esri | Esri Master License | Multi-scale Vector/Raster | Dynamic Cloud | ArcGIS API Key | REST Standardized |

---

## Detailed Connector Specifications

### 1. Copernicus Sentinel-1 Synthetic Aperture Radar (SAR)
- **Primary Use:** Microwave surface backscatter change detection for all-weather flood inundation extraction during monsoon cloud cover.
- **Acquisition Mode:** Interferometric Wide (IW) swath Ground Range Detected (GRD) in VV+VH polarization.
- **Endpoint:** `https://catalogue.dataspace.copernicus.eu/odata/v1/Products`
- **Fallback Rule:** If CDSE credentials are not supplied, metadata is discovered through the public OData catalog and verified historical Sentinel-1 scenes covering Mumbai are served.

### 2. Copernicus Sentinel-2 Optical MultiSpectral Instrument (MSI)
- **Primary Use:** Normalized Difference Water Index (NDWI), Normalized Difference Built-up Index (NDBI), and impervious surface baseline characterization.
- **Tile Coverage:** Sentinel-2 Tile `43QDA` and `43QEA`.
- **Endpoint:** CDSE OData / STAC API.

### 3. NASA Global Precipitation Measurement (GPM) IMERG
- **Primary Use:** Daily precipitation time-series and antecedent rainfall indices.
- **Endpoint:** `https://power.larc.nasa.gov/api/temporal/daily/point` & NASA CMR Granule search.
- **Live Status:** Fully active with live precipitation queries for Mumbai coordinates (`19.076° N, 72.877° E`).

### 4. Copernicus Digital Elevation Model (GLO-30)
- **Primary Use:** Topographic wetness index, depression storage, and slope computation.
- **Coverage:** Bounding box covering Mumbai island city, Salsette island, and Trombay/Powai ridges.
- **Endpoint:** Open-Elevation REST service & OpenTopography Global DEM API.

### 5. OpenStreetMap (OSM)
- **Primary Use:** Real-time arterial roads, bridges, subways, hospitals, and educational facilities.
- **Endpoint:** `https://overpass-api.de/api/interpreter`
- **Live Status:** Active live queries over Mumbai bounding box `[18.89, 72.78, 19.29, 72.99]`.

### 6. WorldPop Gridded Population (IND)
- **Primary Use:** Disaggregated 100m demographic exposure estimation inside flood polygons.
- **Methodology:** Random Forest dasymetric redistribution constrained by building footprints.

### 7. Global Flood Database (DFO)
- **Primary Use:** Retrospective validation for July 2005 (DFO 2841) and August 2017 (DFO 4512) Mumbai deluges.

### 8. India Meteorological Department (IMD) AWS
- **Primary Use:** Real-time rain gauge benchmarks from Santacruz (Station 43003) and Colaba (Station 43057).
- **Setup:** Documented in [SETUP_GUIDE.md](file:///c:/Projects/capstone_project/docs/SETUP_GUIDE.md).
