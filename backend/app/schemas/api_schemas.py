from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import List, Optional, Dict, Any
from datetime import datetime

# --- Health & Reliability Schemas (Phase 7F) ---
class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    postgis_enabled: bool
    data_freshness_timestamp: datetime
    geospatial_engine: str

class LivenessResponse(BaseModel):
    status: str = "ok"
    timestamp: datetime
    uptime_seconds: float
    process_id: int

class ReadinessResponse(BaseModel):
    status: str  # ready, degraded, not_ready
    database: str
    database_latency_ms: float
    postgis_enabled: bool
    geospatial_engine: str
    dependencies: Dict[str, str]

class DataReadinessResponse(BaseModel):
    status: str  # current, stale, unseeded
    data_freshness_timestamp: Optional[datetime] = None
    observation_count_24h: int
    active_alerts_count: int
    study_areas_total: int
    study_areas_verified: int
    routing_network_ready: bool
    hazard_models_ready: bool
    coverage_gaps_count: int
    known_limitations: List[str]

# --- Study Area Schemas (Phase 7B) ---
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
    parent_region_id: Optional[str] = None
    region_type: Optional[str] = "Ward"
    hierarchy_path: Optional[str] = None
    aliases: Optional[List[str]] = None
    division_id: Optional[str] = None
    district_id: Optional[str] = None
    crs: Optional[str] = "EPSG:4326"
    boundary_version: Optional[str] = None
    effective_date: Optional[datetime] = None
    is_verified: Optional[bool] = True

class StudyAreaResponse(StudyAreaBase):
    model_config = ConfigDict(from_attributes=True)
    created_at: Optional[datetime] = None

# --- Regional Ingestion Schemas (Phase 7C) ---
class RegionalTileResponse(BaseModel):
    tile_id: str
    district_id: str
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float
    status: str
    retry_count: int
    last_ingested_at: Optional[datetime] = None
    data_hash: Optional[str] = None
    records_count: int
    error_message: Optional[str] = None

class RegionalIngestionSummaryResponse(BaseModel):
    timestamp: datetime
    total_tiles: int
    completed_tiles: int
    failed_tiles: int
    in_progress_tiles: int
    idle_tiles: int
    statewide_coverage_percentage: float
    district_tile_counts: Dict[str, Dict[str, int]]
    coverage_gaps_count: int
    coverage_gaps: List[Dict[str, Any]]
    provenance_note: str

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
    model_config = ConfigDict(from_attributes=True)

class WeatherSummaryResponse(BaseModel):
    study_area_id: str
    latest_observation: WeatherObservationResponse
    past_24h_rainfall_mm: float
    rainfall_trend_7d: List[Dict[str, Any]]
    forecast_next_24h_mm: float
    alert_level: str

# --- Satellite Observation Schemas ---
class SatelliteObservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    observation_id: str
    acquisition_time: datetime
    sensor: str
    product_identifier: str
    footprint: Dict[str, Any]
    raster_location: Optional[str] = None
    processing_status: str
    source_metadata: Optional[Dict[str, Any]] = None

# --- Infrastructure Schemas ---
class InfrastructureBase(BaseModel):
    infrastructure_id: str
    feature_type: str
    name: str
    geometry: Dict[str, Any]
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    ward_id: Optional[str] = None
    locality_name: Optional[str] = None
    sub_ward: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    source: str

class InfrastructureResponse(InfrastructureBase):
    model_config = ConfigDict(from_attributes=True)

class RoadSegmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    road_segment_id: str
    name: Optional[str] = None
    road_class: str
    geometry: Dict[str, Any]
    length_meters: Optional[float] = None
    speed_kmh: Optional[float] = None
    locality_name: Optional[str] = None
    elevation_m: Optional[float] = None
    connectivity_attributes: Optional[Dict[str, Any]] = None
    vulnerability_index: Optional[float] = 0.0
    source: str

# --- Building Schemas (MMR Regional Digital Twin) ---
class BuildingBase(BaseModel):
    building_id: str
    name: Optional[str] = None
    building_type: str = "residential"
    study_area_id: Optional[str] = None
    locality_name: Optional[str] = None
    geometry: Dict[str, Any]
    centroid: Optional[List[float]] = None
    height_m: Optional[float] = None
    levels: Optional[int] = None
    ground_elevation_m: Optional[float] = None
    vulnerability_index: Optional[float] = 0.0
    properties: Optional[Dict[str, Any]] = None
    source: str = "OpenStreetMap"

class BuildingResponse(BuildingBase):
    model_config = ConfigDict(from_attributes=True)
    created_at: Optional[datetime] = None

# --- Locality Early Warning Alert Schemas ---
class LocalityAlertBase(BaseModel):
    alert_id: str
    locality_name: str
    study_area_id: Optional[str] = None
    severity_level: str  # GREEN, YELLOW, ORANGE, RED
    headline: str
    description: str
    expected_water_depth_m: Optional[float] = None
    onset_timestamp: Optional[datetime] = None
    expiry_timestamp: Optional[datetime] = None
    recommended_action: Optional[str] = None
    source: str = "EIDT Flood Early Warning Engine"
    is_active: bool = True

class LocalityAlertResponse(LocalityAlertBase):
    model_config = ConfigDict(from_attributes=True)
    created_at: Optional[datetime] = None

# --- Data Provenance Log Schemas ---
class DataProvenanceLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    log_id: str
    source_id: str
    connector_name: str
    retrieval_timestamp: datetime
    status: str
    records_ingested: int = 0
    spatial_extent: Optional[Dict[str, Any]] = None
    checksum: Optional[str] = None
    details: Optional[str] = None

# --- Flood Events ---
class FloodEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    event_id: str
    event_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    peak_rainfall_mm_24h: Optional[float] = None
    observed_extent: Dict[str, Any]
    study_area_id: Optional[str] = None
    source: str
    confidence_notes: Optional[str] = None

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
    model_config = ConfigDict(from_attributes=True)
    scenario_id: str
    study_area_id: str
    scenario_name: str
    rainfall_total_mm: float
    duration_hours: float
    assumptions: Dict[str, Any]
    mitigation_features: Optional[Dict[str, Any]] = None
    model_run_id: Optional[str] = None
    created_at: datetime

class SimulationResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    result_id: str
    scenario_id: str
    result_type: str
    result_location: Optional[str] = None
    summary_metrics: Dict[str, Any]
    ward_breakdown: Optional[Dict[str, Any]] = None
    uncertainty_metadata: Optional[Dict[str, Any]] = None
    generated_at: datetime

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


# =========================================================================
# Phase 2A: Flood Hazard Module Schemas
# =========================================================================

class HourlyPrecipitationPoint(BaseModel):
    valid_time: datetime
    precipitation_mm: float
    rain_mm: Optional[float] = None
    precipitation_probability_pct: Optional[float] = None
    weather_code: Optional[int] = None

class ForecastSummaryMetrics(BaseModel):
    accumulation_1h_max_mm: float
    accumulation_3h_max_mm: float
    accumulation_6h_max_mm: float
    accumulation_12h_max_mm: float
    accumulation_24h_total_mm: float
    peak_intensity_timestamp: Optional[datetime] = None
    heavy_rain_hours_count: int = 0

class FloodForecastResponse(BaseModel):
    issue_time: datetime
    retrieval_time: datetime
    valid_start_time: datetime
    valid_end_time: datetime
    horizon_hours: int = 24
    source: str = "Open-Meteo"
    provider: str = "Open-Meteo Weather API (ECMWF/GFS synthesis)"
    model_name: str = "best_match"
    attribution: str = "Weather data by Open-Meteo.com under CC BY 4.0"
    coordinates: Dict[str, float]
    units: Dict[str, str]
    hourly_forecast: List[HourlyPrecipitationPoint]
    summary_metrics: ForecastSummaryMetrics

class LocalityFloodRiskItem(BaseModel):
    locality_id: str
    locality_name: str
    study_area_id: str
    ward_name: str
    centroid: List[float]
    elevation_mean_m: Optional[float] = None
    rainfall_forecast_24h_mm: float
    rainfall_forecast_peak_1h_mm: float
    rainfall_forecast_peak_3h_mm: float
    antecedent_rainfall_24h_mm: float
    risk_level: str  # LOW, MODERATE, HIGH, CRITICAL
    risk_score: float
    contributing_factors: List[str]
    missing_inputs: List[str]
    input_coverage: Dict[str, str]
    confidence_status: str
    model_version: str

class LocalityFloodRiskListResponse(BaseModel):
    assessment_time: datetime
    forecast_issue_time: datetime
    horizon_hours: int = 24
    study_region: str
    total_localities_assessed: int
    risk_distribution: Dict[str, int]
    data_quality_summary: Dict[str, Any]
    localities: List[LocalityFloodRiskItem]

class FloodModuleStatusResponse(BaseModel):
    module_name: str
    status: str
    version: str
    active_spatial_engine: str
    geographic_coverage: str
    connectors: Dict[str, Any]
    scientific_notice: str
    limitations: List[str]

class FloodObservationBenchmarkItem(BaseModel):
    event_id: str
    event_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    peak_rainfall_mm_24h: Optional[float] = None
    source: str
    license: str = "CC BY 4.0"
    observed_extent: Dict[str, Any]
    confidence_notes: Optional[str] = None
    data_type: str = "OBSERVED_HISTORICAL_DATA"

class FloodAlertItem(BaseModel):
    alert_id: str
    locality_name: str
    study_area_id: Optional[str] = None
    severity_level: str  # GREEN, YELLOW, ORANGE, RED
    headline: str
    description: str
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    source: str
    recommended_action: Optional[str] = None
    is_official_agency: bool = False
    status: str  # ACTIVE, ADVISORY, UNAVAILABLE


# --- Inundation Simulation Schemas (Phase 2C) ---
class InundationSimulateRequest(BaseModel):
    study_area_id: str = "MUM_WARD_L_KURLA"
    rainfall_scenario_mm: float = Field(200.0, ge=1.0, le=1500.0, description="Rainfall accumulation in mm")
    duration_hours: float = Field(24.0, ge=1.0, le=168.0, description="Storm duration in hours")
    tide_level_m: float = Field(4.2, ge=0.0, le=7.0, description="Arabian Sea high-tide level in metres CD")
    soil_saturation_pct: float = Field(75.0, ge=0.0, le=100.0, description="Soil saturation percentage (AMC I/II/III)")
    run_name: Optional[str] = None
    force_rerun: bool = False

class InundationSimulationResponse(BaseModel):
    simulation_id: str
    study_area_id: str
    run_name: str
    model_type: str
    model_version: str
    product_classification: str
    status: str
    spatial_resolution_m: float
    inputs: Dict[str, Any]
    summary_metrics: Dict[str, Any]
    asset_exposure: Dict[str, Any]
    depth_distribution: Dict[str, Any]
    execution_duration_sec: float
    created_at_utc: Optional[str] = None
    input_provenance: Dict[str, Any]
    uncertainty_metadata: Dict[str, Any]
    limitation_notes: Optional[str] = None

class RoadDisruptionRequest(BaseModel):
    origin_coords: List[float] = Field(..., description="[longitude, latitude]")
    dest_facility_id: Optional[str] = Field(None, description="Destination hospital or emergency node ID")
    rainfall_scenario_mm: float = Field(200.0, ge=1.0, le=1500.0)
    tide_level_m: float = Field(4.2, ge=0.0, le=7.0)


# --- Emergency Facilities & Evacuation Schemas (Phase 4) ---
class EmergencyFacilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    facility_id: str
    source_id: Optional[str] = None
    source_name: str
    name: str
    facility_type: str
    latitude: float
    longitude: float
    locality_name: Optional[str] = None
    ward_id: Optional[str] = None
    verification_status: str
    operating_status: str
    contact_phone: Optional[str] = None
    capacity_total: Optional[int] = None
    capacity_available: Optional[int] = None
    capacity_status_notes: Optional[str] = None
    is_officially_designated_shelter: bool = False
    accessibility_notes: Optional[str] = None
    provenance_url: Optional[str] = None


class FacilityNearbyQuery(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    radius_km: float = Field(5.0, ge=0.1, le=50.0)
    facility_type: Optional[str] = None
    shelter_only: bool = False


class RouteCalculateRequest(BaseModel):
    origin_lat: Optional[float] = Field(None, ge=-90.0, le=90.0, description="Origin latitude in WGS-84")
    origin_lon: Optional[float] = Field(None, ge=-180.0, le=180.0, description="Origin longitude in WGS-84")
    destination_lat: Optional[float] = Field(None, ge=-90.0, le=90.0, description="Destination latitude in WGS-84")
    destination_lon: Optional[float] = Field(None, ge=-180.0, le=180.0, description="Destination longitude in WGS-84")
    origin_latitude: Optional[float] = None
    origin_longitude: Optional[float] = None
    destination_latitude: Optional[float] = None
    destination_longitude: Optional[float] = None
    destination_facility_id: Optional[str] = None
    routing_mode: str = Field("HAZARD_AWARE_SAFE", description="SHORTEST_DISTANCE, FASTEST_TIME, HAZARD_AWARE_SAFE, SCENARIO_TEST")
    routing_cost: Optional[str] = None
    avoid_waterlogged: bool = Field(True, description="Penalize waterlogged roads")
    avoid_closed_roads: bool = Field(True, description="Avoid verified closed roads")
    include_alternatives: bool = Field(True, description="Compute secondary distinct corridor alternative")
    k_alternatives: int = Field(2, ge=1, le=5)
    is_hypothetical_scenario: bool = Field(False)
    scenario_id: Optional[str] = Field(None, description="Hypothetical road closure scenario ID if testing")

    @model_validator(mode='before')
    @classmethod
    def reconcile_coordinates(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if data.get("origin_lat") is None and "origin_latitude" in data:
                data["origin_lat"] = data["origin_latitude"]
            if data.get("origin_lon") is None and "origin_longitude" in data:
                data["origin_lon"] = data["origin_longitude"]
            if data.get("destination_lat") is None and "destination_latitude" in data:
                data["destination_lat"] = data["destination_latitude"]
            if data.get("destination_lon") is None and "destination_longitude" in data:
                data["destination_lon"] = data["destination_longitude"]
            if "routing_cost" in data and ("routing_mode" not in data or data["routing_mode"] == "HAZARD_AWARE_SAFE"):
                cost = str(data["routing_cost"]).lower()
                if "short" in cost:
                    data["routing_mode"] = "SHORTEST_DISTANCE"
                elif "fast" in cost:
                    data["routing_mode"] = "FASTEST_TIME"
                else:
                    data["routing_mode"] = "HAZARD_AWARE_SAFE"
        return data


class NearestFacilityRequest(BaseModel):
    origin_lat: Optional[float] = Field(None, ge=-90.0, le=90.0)
    origin_lon: Optional[float] = Field(None, ge=-180.0, le=180.0)
    origin_latitude: Optional[float] = None
    origin_longitude: Optional[float] = None
    facility_type: Optional[str] = Field("hospital", description="hospital, shelter, evacuation_shelter, fire_station, police_station, all")
    shelter_only: bool = Field(False, description="Filter strictly to officially designated evacuation shelters")
    routing_mode: str = Field("HAZARD_AWARE_SAFE", description="SHORTEST_DISTANCE, FASTEST_TIME, HAZARD_AWARE_SAFE")
    routing_cost: Optional[str] = None
    avoid_waterlogged: bool = True
    avoid_closed_roads: bool = True
    is_hypothetical_scenario: bool = False
    scenario_id: Optional[str] = None

    @model_validator(mode='before')
    @classmethod
    def reconcile_nearest(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if data.get("origin_lat") is None and "origin_latitude" in data:
                data["origin_lat"] = data["origin_latitude"]
            if data.get("origin_lon") is None and "origin_longitude" in data:
                data["origin_lon"] = data["origin_longitude"]
            if "routing_cost" in data:
                cost = str(data["routing_cost"]).lower()
                if "short" in cost:
                    data["routing_mode"] = "SHORTEST_DISTANCE"
                elif "fast" in cost:
                    data["routing_mode"] = "FASTEST_TIME"
                else:
                    data["routing_mode"] = "HAZARD_AWARE_SAFE"
            if data.get("facility_type") == "shelter":
                data["facility_type"] = "evacuation_shelter"
                data["shelter_only"] = True
        return data


class RoadRestrictionCreateRequest(BaseModel):
    road_name: str
    road_segment_id: Optional[str] = None
    restriction_type: str = "CLOSURE_FLOOD"
    severity: str = "BLOCKED"
    is_hypothetical_scenario: bool = True
    scenario_id: Optional[str] = None
    cause_description: str
    issuing_authority: str = "EIDT Emergency Scenario Planner"
    valid_hours: int = 24


class EvacuationAssessRequest(BaseModel):
    ward_id: Optional[str] = "MUM_WARD_L_KURLA"
    ward_ids: Optional[List[str]] = None
    rainfall_scenario: Optional[str] = "SCEN_HEAVY_200MM"
    rainfall_scenario_mm: float = Field(200.0, ge=1.0, le=1500.0)
    evacuation_demand_pct: float = Field(5.0, ge=0.5, le=100.0, description="Estimated % of ward population requiring municipal shelter")


class EvacuationScenarioCreateRequest(BaseModel):
    name: Optional[str] = None
    scenario_name: Optional[str] = None
    description: Optional[str] = None
    scenario_type: Optional[str] = "hypothetical_road_closure"
    target_ward_id: Optional[str] = "MUM_WARD_L_KURLA"
    closed_corridors: List[str] = Field(default_factory=list, description="Road names to mark as impassable")
    hypothetical_restrictions: Optional[List[Dict[str, Any]]] = None
    flood_depth_threshold_cm: float = 30.0

    @model_validator(mode='before')
    @classmethod
    def reconcile_scenario(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("name") and data.get("scenario_name"):
                data["name"] = data["scenario_name"]
            elif data.get("name") and not data.get("scenario_name"):
                data["scenario_name"] = data["name"]
        return data



