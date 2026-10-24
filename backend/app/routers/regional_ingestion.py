"""
Regional Data Ingestion Router
Earth Intelligence Digital Twin (EIDT) - Maharashtra
Phase 7C: Tiled Ingestion, Checkpointing & Statewide Gap Reporting.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional

from app.database import get_db
from app.models.schema import RegionalIngestionTile
from app.schemas.api_schemas import RegionalTileResponse, RegionalIngestionSummaryResponse
from app.services.spatial_tiling import (
    generate_district_tiles, get_pending_tiles, ingest_tile, get_regional_ingestion_summary
)

router = APIRouter(prefix="/regional-ingestion", tags=["Regional Ingestion & Spatial Tiling"])


@router.post("/generate-tiles", response_model=List[RegionalTileResponse])
def create_district_tiles(
    district_id: str = Query(..., description="Target district ID (e.g. DIST_PUNE, DIST_THANE)"),
    tile_size_deg: float = Query(0.25, description="Spatial tile resolution in degrees (default 0.25°)"),
    db: Session = Depends(get_db)
):
    """Generates 0.25° spatial bounding tiles for a Maharashtra district."""
    tiles = generate_district_tiles(district_id, db, tile_size_deg)
    if not tiles:
        raise HTTPException(status_code=404, detail=f"District '{district_id}' not found or has no bounding box.")
    return tiles


@router.get("/tiles", response_model=List[RegionalTileResponse])
def list_tiles(
    district_id: Optional[str] = Query(None, description="Filter by district"),
    status: Optional[str] = Query(None, description="Filter by status (IDLE, COMPLETED, FAILED, RETRYING)"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Lists regional spatial ingestion tiles with status and district filtering."""
    query = db.query(RegionalIngestionTile)
    if district_id:
        query = query.filter(RegionalIngestionTile.district_id == district_id)
    if status:
        query = query.filter(RegionalIngestionTile.status == status)
    return query.limit(limit).all()


@router.post("/ingest-tile")
def run_tile_ingestion(
    tile_id: str = Query(..., description="Tile ID to ingest"),
    source_type: str = Query("WEATHER_IMD", description="Source profile (WEATHER_IMD, TERRAIN_DEM, ROADS_OSM)"),
    dry_run: bool = Query(False, description="Dry-run simulation mode"),
    db: Session = Depends(get_db)
):
    """Executes checkpointed bounded ingestion for a spatial tile."""
    res = ingest_tile(tile_id, source_type, db, dry_run)
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res)
    return res


@router.get("/summary", response_model=RegionalIngestionSummaryResponse)
def get_ingestion_summary(db: Session = Depends(get_db)):
    """
    Returns statewide ingestion metrics across all 36 districts:
    Total tiles, completed tiles, failed tiles, coverage percentage, and explicit coverage gaps.
    """
    return get_regional_ingestion_summary(db)
