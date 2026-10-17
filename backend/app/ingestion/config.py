"""
Central Configuration for Earth Intelligence Digital Twin (EIDT)
Automated Data Acquisition and Extraction Pipeline
"""
import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict, Any

# Locate and load root .env
ROOT_ENV = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"))
if os.path.exists(ROOT_ENV):
    load_dotenv(ROOT_ENV)
else:
    load_dotenv()

class IngestionConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_ENV if os.path.exists(ROOT_ENV) else ".env", extra="ignore")

    # Geographic Scope: Greater Mumbai Metropolitan Study Area
    STUDY_AREA_NAME: str = "Mumbai Metropolitan Region"
    MUMBAI_BBOX: Dict[str, float] = {
        "min_lon": 72.780,
        "min_lat": 18.890,
        "max_lon": 72.990,
        "max_lat": 19.290
    }
    TARGET_CRS: str = "EPSG:4326"
    PROJECTED_CRS: str = "EPSG:32643"  # UTM Zone 43N (meters)

    # Directories
    BASE_DIR: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    RAW_DIR: str = os.path.join(BASE_DIR, "data", "raw")
    PROCESSED_DIR: str = os.path.join(BASE_DIR, "data", "processed")

    # API Credentials & Endpoints (All securely configured from environment)
    # 1. Copernicus Data Space Ecosystem (CDSE)
    CDSE_CLIENT_ID: str = os.getenv("CDSE_CLIENT_ID", "")
    CDSE_CLIENT_SECRET: str = os.getenv("CDSE_CLIENT_SECRET", "")
    CDSE_ODATA_ENDPOINT: str = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
    CDSE_AUTH_URL: str = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"

    # 2. NASA Earthdata (GPM IMERG)
    EARTHDATA_USERNAME: str = os.getenv("EARTHDATA_USERNAME", "")
    EARTHDATA_PASSWORD: str = os.getenv("EARTHDATA_PASSWORD", "")
    EARTHDATA_CMR_ENDPOINT: str = "https://cmr.earthdata.nasa.gov/search/granules.json"
    NASA_POWER_ENDPOINT: str = "https://power.larc.nasa.gov/api/temporal/daily/point"

    # 3. Elevation
    OPEN_ELEVATION_ENDPOINT: str = "https://api.open-elevation.com/api/v1/lookup"
    OPEN_TOPO_ENDPOINT: str = "https://portal.opentopography.org/API/globaldem"
    OPEN_TOPO_API_KEY: str = os.getenv("OPEN_TOPO_API_KEY", "")

    # 4. OpenStreetMap
    OVERPASS_ENDPOINT: str = os.getenv("OVERPASS_ENDPOINT", "https://overpass-api.de/api/interpreter")

    # 5. WorldPop
    WORLDPOP_API_ENDPOINT: str = "https://hub.worldpop.org/rest/data/pop/wpgp"

    # 6. Global Flood Database / DFO
    DFO_ARCHIVE_URL: str = "https://floodobservatory.colorado.edu/Version3/ActiveArchive/"

    # 7. India Meteorological Department (IMD)
    IMD_API_KEY: str = os.getenv("IMD_API_KEY", "")
    IMD_AWS_PORTAL: str = "https://mausam.imd.gov.in"

    # 8. Google Maps Platform (Maps JavaScript API & Map Tiles)
    GOOGLE_MAPS_API_KEY: str = os.getenv("GOOGLE_MAPS_API_KEY", os.getenv("VITE_GOOGLE_MAPS_API_KEY", ""))
    ARCGIS_API_KEY: str = ""  # Deprecated backward compatibility
    ARCGIS_REST_URL: str = "https://services.arcgis.com"

    # Pipeline Operation Mode
    # If credentials are not present, connectors record STATUS_MISSING_CREDENTIALS and switch to documented sample mode
    ALLOW_DEMO_FALLBACK: bool = True
    REQUEST_TIMEOUT_SECONDS: int = 25
    MAX_RETRIES: int = 3

ingestion_config = IngestionConfig()
