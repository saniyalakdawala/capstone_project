"""
Study Areas & Maharashtra Spatial Hierarchy Router
Earth Intelligence Digital Twin (EIDT) - Maharashtra
Phase 7B & 7E: Statewide Hierarchy, Viewport Spatial Filtering & Level-of-Detail Simplification.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from app.database import get_db
from app.models.schema import StudyArea
from app.schemas.api_schemas import StudyAreaResponse
from app.services.geo_hierarchy import (
    simplify_geometry_for_zoom, resolve_locality_by_alias,
    validate_polygon_topology, seed_maharashtra_hierarchy
)

router = APIRouter(prefix="/study-areas", tags=["Study Areas & Spatial Hierarchy"])


@router.get("", response_model=List[StudyAreaResponse])
def list_study_areas(
    region_type: Optional[str] = Query(None, description="Filter by State, Division, District, or Ward"),
    division_id: Optional[str] = Query(None, description="Filter by parent division ID"),
    district_id: Optional[str] = Query(None, description="Filter by parent district ID"),
    min_lat: Optional[float] = Query(None, description="Viewport min latitude"),
    min_lon: Optional[float] = Query(None, description="Viewport min longitude"),
    max_lat: Optional[float] = Query(None, description="Viewport max latitude"),
    max_lon: Optional[float] = Query(None, description="Viewport max longitude"),
    alias: Optional[str] = Query(None, description="Search by multilingual alias or alternate spelling"),
    db: Session = Depends(get_db)
):
    """
    Retrieves study areas with optional spatial bounding-box filtering,
    hierarchy filtering, and alias resolution.
    """
    if alias:
        resolved = resolve_locality_by_alias(alias, db)
        return [resolved] if resolved else []

    query = db.query(StudyArea)

    if region_type:
        query = query.filter(StudyArea.region_type == region_type)
    if division_id:
        query = query.filter(StudyArea.division_id == division_id)
    if district_id:
        query = query.filter(StudyArea.district_id == district_id)

    areas = query.all()

    # Apply spatial bounding-box intersection filtering if provided
    if all(v is not None for v in [min_lat, min_lon, max_lat, max_lon]):
        filtered = []
        for a in areas:
            if a.bounding_box and len(a.bounding_box) == 4:
                b_min_lat, b_min_lon, b_max_lat, b_max_lon = a.bounding_box
                # Check bounding box overlap:
                # not (b_max_lat < min_lat or b_min_lat > max_lat or b_max_lon < min_lon or b_min_lon > max_lon)
                if not (b_max_lat < min_lat or b_min_lat > max_lat or b_max_lon < min_lon or b_min_lon > max_lon):
                    filtered.append(a)
        return filtered

    return areas


@router.get("/geojson")
def get_study_areas_geojson(
    region_type: Optional[str] = Query(None, description="Filter by State, Division, District, or Ward"),
    division_id: Optional[str] = Query(None, description="Filter by division ID"),
    zoom: Optional[int] = Query(14, description="Map zoom level for dynamic Douglas-Peucker simplification"),
    min_lat: Optional[float] = Query(None, description="Viewport min latitude"),
    min_lon: Optional[float] = Query(None, description="Viewport min longitude"),
    max_lat: Optional[float] = Query(None, description="Viewport max latitude"),
    max_lon: Optional[float] = Query(None, description="Viewport max longitude"),
    db: Session = Depends(get_db)
):
    """
    Returns study areas formatted directly as a GeoJSON FeatureCollection.
    Features:
      - Multi-scale Douglas-Peucker simplification based on current zoom level.
      - Server-side bounding-box viewport clipping to prevent client payload bloat.
    """
    query = db.query(StudyArea)
    if region_type:
        query = query.filter(StudyArea.region_type == region_type)
    if division_id:
        query = query.filter(StudyArea.division_id == division_id)

    areas = query.all()

    # Bbox filtering
    has_bbox = all(v is not None for v in [min_lat, min_lon, max_lat, max_lon])

    features = []
    for w in areas:
        if has_bbox and w.bounding_box and len(w.bounding_box) == 4:
            b_min_lat, b_min_lon, b_max_lat, b_max_lon = w.bounding_box
            if b_max_lat < min_lat or b_min_lat > max_lat or b_max_lon < min_lon or b_min_lon > max_lon:
                continue

        # Dynamic Level-of-Detail geometry simplification for lower zoom levels
        display_geometry = simplify_geometry_for_zoom(w.geometry, zoom) if zoom and zoom < 13 else w.geometry

        features.append({
            "type": "Feature",
            "properties": {
                "study_area_id": w.study_area_id,
                "name": w.name,
                "administrative_level": w.administrative_level,
                "area_sq_km": float(w.area_sq_km or 0),
                "population": w.population,
                "elevation_mean_m": float(w.elevation_mean_m or 0),
                "source": w.source,
                "parent_region_id": w.parent_region_id,
                "region_type": w.region_type or "Ward",
                "hierarchy_path": w.hierarchy_path,
                "division_id": w.division_id,
                "district_id": w.district_id,
                "aliases": w.aliases or [],
                "crs": w.crs or "EPSG:4326",
                "boundary_version": w.boundary_version,
                "is_verified": w.is_verified
            },
            "geometry": display_geometry
        })

    return {
        "type": "FeatureCollection",
        "features": features
    }


@router.post("/seed-hierarchy")
def trigger_seed_hierarchy(db: Session = Depends(get_db)):
    """Idempotently seeds/synchronizes the full Maharashtra administrative hierarchy."""
    result = seed_maharashtra_hierarchy(db)
    return {
        "message": "Maharashtra statewide geographic hierarchy seeded successfully.",
        "counts": result
    }


@router.get("/{study_area_id}", response_model=StudyAreaResponse)
def get_study_area(study_area_id: str, db: Session = Depends(get_db)):
    ward = db.query(StudyArea).filter(StudyArea.study_area_id == study_area_id).first()
    if not ward:
        raise HTTPException(status_code=404, detail=f"Study area '{study_area_id}' not found.")
    return ward
