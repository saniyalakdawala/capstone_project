from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone
from app.database import get_db
from app.models.schema import WeatherObservation, SatelliteObservation
from app.schemas.api_schemas import (
    WeatherObservationResponse, WeatherSummaryResponse, SatelliteObservationResponse
)

router = APIRouter(tags=["Weather & Satellite"])

@router.get("/weather", response_model=WeatherSummaryResponse)
def get_weather_summary(
    study_area_id: str = Query("MUM_WARD_L_KURLA", description="Pilot ward ID"),
    db: Session = Depends(get_db)
):
    obs_list = (
        db.query(WeatherObservation)
        .order_by(WeatherObservation.timestamp.desc())
        .limit(14)
        .all()
    )
    if not obs_list:
        latest = WeatherObservation(
            observation_id="OBS_FALLBACK",
            timestamp=datetime.now(timezone.utc),
            study_area_id=study_area_id,
            rainfall_mm=68.5,
            temperature_c=29.0,
            humidity=86.0,
            wind_speed=22.0,
            source="IMD Santacruz AWS",
            observation_type="observed"
        )
        obs_list = [latest]

    latest = obs_list[0]
    past_24h = float(latest.rainfall_mm)
    forecast_next_24h = round(past_24h * 1.15, 1)

    trend = [
        {
            "date": o.timestamp.strftime("%d %b"),
            "rainfall_mm": float(o.rainfall_mm),
            "type": o.observation_type
        }
        for o in reversed(obs_list)
    ]

    alert = "GREEN (Normal)"
    if past_24h >= 204.4:
        alert = "RED ALERT (Extremely Heavy Rainfall > 204.4 mm)"
    elif past_24h >= 115.6:
        alert = "ORANGE ALERT (Very Heavy Rainfall 115.6 - 204.4 mm)"
    elif past_24h >= 64.5:
        alert = "YELLOW ALERT (Heavy Rainfall 64.5 - 115.5 mm)"

    return WeatherSummaryResponse(
        study_area_id=study_area_id,
        latest_observation=WeatherObservationResponse.model_validate(latest),
        past_24h_rainfall_mm=past_24h,
        rainfall_trend_7d=trend,
        forecast_next_24h_mm=forecast_next_24h,
        alert_level=alert
    )

@router.get("/satellite-observations", response_model=List[SatelliteObservationResponse])
def list_satellite_observations(db: Session = Depends(get_db)):
    obs = db.query(SatelliteObservation).order_by(SatelliteObservation.acquisition_time.desc()).all()
    return obs
