from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timezone
from app.database import get_db
from app.schemas.api_schemas import HealthResponse

router = APIRouter(prefix="/health", tags=["Health & System"])

@router.get("", response_model=HealthResponse)
def get_health(db: Session = Depends(get_db)):
    db_status = "connected"
    postgis_enabled = False
    try:
        # Check if database is active and if postgis extension is installed
        result = db.execute(text("SELECT extname FROM pg_extension WHERE extname = 'postgis';"))
        row = result.fetchone()
        postgis_enabled = bool(row)
    except Exception:
        # In SQLite or when pg_extension is unavailable
        try:
            db.execute(text("SELECT 1;"))
            db_status = "connected (standard SQL mode)"
        except Exception as e:
            db_status = f"unhealthy: {e}"

    return HealthResponse(
        status="operational",
        version="1.0.0",
        database=db_status,
        postgis_enabled=postgis_enabled,
        data_freshness_timestamp=datetime.now(timezone.utc),
        geospatial_engine="GeoPandas + Shapely 2.0 + PostGIS Spatial Engine"
    )
