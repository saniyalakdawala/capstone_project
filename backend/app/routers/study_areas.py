from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from app.database import get_db
from app.models.schema import StudyArea
from app.schemas.api_schemas import StudyAreaResponse

router = APIRouter(prefix="/study-areas", tags=["Study Areas"])

@router.get("", response_model=List[StudyAreaResponse])
def list_study_areas(db: Session = Depends(get_db)):
    wards = db.query(StudyArea).all()
    return wards

@router.get("/geojson")
def get_study_areas_geojson(db: Session = Depends(get_db)):
    """Returns study areas formatted directly as a GeoJSON FeatureCollection"""
    wards = db.query(StudyArea).all()
    features = []
    for w in wards:
        features.append({
            "type": "Feature",
            "properties": {
                "study_area_id": w.study_area_id,
                "name": w.name,
                "administrative_level": w.administrative_level,
                "area_sq_km": float(w.area_sq_km or 0),
                "population": w.population,
                "elevation_mean_m": float(w.elevation_mean_m or 0),
                "source": w.source
            },
            "geometry": w.geometry
        })
    return {
        "type": "FeatureCollection",
        "features": features
    }

@router.get("/{study_area_id}", response_model=StudyAreaResponse)
def get_study_area(study_area_id: str, db: Session = Depends(get_db)):
    ward = db.query(StudyArea).filter(StudyArea.study_area_id == study_area_id).first()
    if not ward:
        raise HTTPException(status_code=404, detail=f"Study area '{study_area_id}' not found.")
    return ward
