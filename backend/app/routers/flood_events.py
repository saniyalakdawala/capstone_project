from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.schema import FloodEvent
from app.schemas.api_schemas import FloodEventResponse

router = APIRouter(prefix="/flood-events", tags=["Historical Flood Events"])

@router.get("", response_model=List[FloodEventResponse])
def get_historical_events(db: Session = Depends(get_db)):
    events = db.query(FloodEvent).order_by(FloodEvent.start_time.desc()).all()
    return events

@router.get("/geojson")
def get_historical_events_geojson(db: Session = Depends(get_db)):
    events = db.query(FloodEvent).all()
    features = []
    for ev in events:
        features.append({
            "type": "Feature",
            "properties": {
                "event_id": ev.event_id,
                "event_name": ev.event_name,
                "start_time": ev.start_time.isoformat(),
                "peak_rainfall_mm_24h": float(ev.peak_rainfall_mm_24h or 0),
                "source": ev.source,
                "notes": ev.confidence_notes
            },
            "geometry": ev.observed_extent
        })
    return {
        "type": "FeatureCollection",
        "features": features
    }
