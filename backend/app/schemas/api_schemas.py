from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

# --- Health Schema ---
class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    postgis_enabled: bool
    data_freshness_timestamp: datetime
    geospatial_engine: str

# --- Study Area Schemas ---
class StudyAreaBase(BaseModel):
    study_area_id: str
    name: str
    administrative_level: str
    geometry: Dict[str, Any]
    bounding_box: Optional[List[float]] = None
    area_sq_km: Optional[float] = None
    population: Optional[int] = None
    elevation_mean_m: Optional[float] = None
    source: str

class StudyAreaResponse(StudyAreaBase):
    created_at: Optional[datetime] = None
    class Config:
        from_attributes = True

# --- Weather Schemas ---
class WeatherObservationBase(BaseModel):
    observation_id: str
    timestamp: datetime
    study_area_id: Optional[str] = None
    rainfall_mm: float
    temperature_c: Optional[float] = None
    humidity: Optional[float] = None
    wind_speed: Optional[float] = None
    source: str
    observation_type: str

class WeatherObservationResponse(WeatherObservationBase):
    class Config:
        from_attributes = True

class WeatherSummaryResponse(BaseModel):
    study_area_id: str
    latest_observation: WeatherObservationResponse
    past_24h_rainfall_mm: float
    rainfall_trend_7d: List[Dict[str, Any]]
    forecast_next_24h_mm: float
    alert_level: str

# --- Satellite Observation Schemas ---
class SatelliteObservationResponse(BaseModel):
    observation_id: str
    acquisition_time: datetime
    sensor: str
    product_identifier: str
    footprint: Dict[str, Any]
    raster_location: Optional[str] = None
    processing_status: str
    source_metadata: Optional[Dict[str, Any]] = None
    class Config:
        from_attributes = True

# --- Infrastructure Schemas ---
class InfrastructureBase(BaseModel):
    infrastructure_id: str
    feature_type: str
    name: str
    geometry: Dict[str, Any]
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    ward_id: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    source: str

class InfrastructureResponse(InfrastructureBase):
    class Config:
        from_attributes = True

class RoadSegmentResponse(BaseModel):
    road_segment_id: str
    name: Optional[str] = None
    road_class: str
    geometry: Dict[str, Any]
    length_meters: Optional[float] = None
    speed_kmh: Optional[float] = None
    connectivity_attributes: Optional[Dict[str, Any]] = None
    vulnerability_index: Optional[float] = 0.0
    source: str
    class Config:
        from_attributes = True

# --- Flood Events ---
class FloodEventResponse(BaseModel):
    event_id: str
    event_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    peak_rainfall_mm_24h: Optional[float] = None
    observed_extent: Dict[str, Any]
    study_area_id: Optional[str] = None
    source: str
    confidence_notes: Optional[str] = None
    class Config:
        from_attributes = True

# --- Scenario & Simulation Schemas ---
class ScenarioCreate(BaseModel):
    study_area_id: str
    scenario_name: str
    rainfall_total_mm: float = Field(..., ge=0, le=1500, description="Total rainfall accumulation in mm")
    duration_hours: float = Field(..., ge=1, le=72, description="Rainfall duration in hours")
    assumptions: Optional[Dict[str, Any]] = Field(
        default_factory=lambda: {
            "soil_saturation_pct": 75,
            "drainage_efficiency_pct": 80,
            "high_tide_height_m": 4.2
        }
    )
    mitigation_features: Optional[Dict[str, Any]] = Field(
        default_factory=lambda: {
            "mithi_river_desilting": False,
            "additional_pumping_stations": False,
            "holding_ponds_active": False
        }
    )

class ScenarioResponse(BaseModel):
    scenario_id: str
    study_area_id: str
    scenario_name: str
    rainfall_total_mm: float
    duration_hours: float
    assumptions: Dict[str, Any]
    mitigation_features: Optional[Dict[str, Any]] = None
    model_run_id: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True

class SimulationResultResponse(BaseModel):
    result_id: str
    scenario_id: str
    result_type: str
    result_location: Optional[str] = None
    summary_metrics: Dict[str, Any]
    ward_breakdown: Optional[Dict[str, Any]] = None
    uncertainty_metadata: Optional[Dict[str, Any]] = None
    generated_at: datetime
    class Config:
        from_attributes = True

# --- Analytics Schemas ---
class ExposureSummary(BaseModel):
    scenario_id: str
    scenario_name: str
    rainfall_mm: float
    total_study_area_km2: float
    high_risk_area_km2: float
    moderate_risk_area_km2: float
    estimated_exposed_population: int
    exposed_hospitals_count: int
    exposed_schools_count: int
    affected_road_segments_count: int
    affected_road_length_km: float
    ward_exposure: List[Dict[str, Any]]
    limitations: List[str]

class RouteAccessibilityRequest(BaseModel):
    origin: List[float] = Field(..., description="[longitude, latitude] of start location")
    destination_facility_id: Optional[str] = None
    scenario_id: Optional[str] = "SCEN_HEAVY_200MM"
    avoid_high_risk_roads: bool = True

class RouteAccessibilityResponse(BaseModel):
    origin: List[float]
    destination: List[float]
    destination_name: str
    status: str  # 'ACCESSIBLE', 'DETOUR_REQUIRED', 'SEVERED'
    baseline_distance_km: float
    scenario_distance_km: float
    delay_minutes: float
    route_geometry: Dict[str, Any]  # GeoJSON LineString
    traversed_segments: List[str]
    inundated_intersections_avoided: int
    advisory: str

# --- Model Metrics Schema ---
class ModelMetricsResponse(BaseModel):
    model_name: str
    model_version: str
    last_evaluated: datetime
    metrics: Dict[str, Any]
    baseline_comparison: Dict[str, Any]
    feature_importance: List[Dict[str, Any]]
    confusion_matrix: Dict[str, Any]
    spatial_kfold_summary: Dict[str, Any]
    scientific_limitations: List[str]
