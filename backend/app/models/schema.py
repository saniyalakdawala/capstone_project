from sqlalchemy import Column, String, Integer, Float, Numeric, DateTime, JSON, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base

class StudyArea(Base):
    __tablename__ = "study_areas"

    study_area_id = Column(String(64), primary_key=True, index=True)
    name = Column(String(128), nullable=False, index=True)
    administrative_level = Column(String(64), default="Ward")
    geometry = Column(JSON, nullable=False)
    bounding_box = Column(JSON, nullable=True)
    area_sq_km = Column(Numeric(10, 4), nullable=True)
    population = Column(Integer, nullable=True)
    elevation_mean_m = Column(Numeric(6, 2), nullable=True)
    source = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    parent_region_id = Column(String(64), ForeignKey("study_areas.study_area_id", ondelete="SET NULL"), nullable=True)
    region_type = Column(String(64), nullable=True, default="Ward")
    hierarchy_path = Column(String(255), nullable=True)
    aliases = Column(JSON, default=list)
    division_id = Column(String(64), nullable=True, index=True)
    district_id = Column(String(64), nullable=True, index=True)
    crs = Column(String(32), default="EPSG:4326")
    boundary_version = Column(String(64), default="SurveyOfIndia-Census2011/MRSAC-v2.1")
    effective_date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    is_verified = Column(Boolean, default=True)
    simplified_geometry = Column(JSON, nullable=True)

    parent_region = relationship("StudyArea", remote_side=[study_area_id], backref="sub_regions")
    weather_observations = relationship("WeatherObservation", back_populates="study_area", cascade="all, delete-orphan")
    scenarios = relationship("Scenario", back_populates="study_area", cascade="all, delete-orphan")
    infrastructure_items = relationship("Infrastructure", back_populates="study_area")
    flood_events = relationship("FloodEvent", back_populates="study_area")
    buildings = relationship("Building", back_populates="study_area")
    locality_alerts = relationship("LocalityAlert", back_populates="study_area")


class WeatherObservation(Base):
    __tablename__ = "weather_observations"

    observation_id = Column(String(64), primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    study_area_id = Column(String(64), ForeignKey("study_areas.study_area_id", ondelete="CASCADE"), nullable=True)
    rainfall_mm = Column(Numeric(8, 2), nullable=False)
    temperature_c = Column(Numeric(5, 2), nullable=True)
    humidity = Column(Numeric(5, 2), nullable=True)
    wind_speed = Column(Numeric(5, 2), nullable=True)
    source = Column(String(128), nullable=False)
    observation_type = Column(String(64), nullable=False)  # 'observed', 'forecast', 'reanalysis', 'simulated'

    study_area = relationship("StudyArea", back_populates="weather_observations")


class SatelliteObservation(Base):
    __tablename__ = "satellite_observations"

    observation_id = Column(String(64), primary_key=True, index=True)
    acquisition_time = Column(DateTime(timezone=True), nullable=False, index=True)
    sensor = Column(String(64), nullable=False)
    product_identifier = Column(String(255), nullable=False)
    footprint = Column(JSON, nullable=False)
    raster_location = Column(String(512), nullable=True)
    processing_status = Column(String(64), nullable=False)
    source_metadata = Column(JSON, nullable=True)


class EnvironmentalFeature(Base):
    __tablename__ = "environmental_features"

    feature_id = Column(String(64), primary_key=True, index=True)
    feature_type = Column(String(64), nullable=False, index=True)
    geometry = Column(JSON, nullable=False)
    elevation = Column(Numeric(6, 2), nullable=True)
    land_cover = Column(String(64), nullable=True)
    imperviousness_pct = Column(Numeric(5, 2), nullable=True)
    slope_degrees = Column(Numeric(5, 2), nullable=True)
    source = Column(String(128), nullable=False)
    observed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Infrastructure(Base):
    __tablename__ = "infrastructure"

    infrastructure_id = Column(String(64), primary_key=True, index=True)
    feature_type = Column(String(64), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    geometry = Column(JSON, nullable=False)
    latitude = Column(Numeric(10, 6), nullable=True)
    longitude = Column(Numeric(10, 6), nullable=True)
    ward_id = Column(String(64), ForeignKey("study_areas.study_area_id"), nullable=True)
    locality_name = Column(String(128), nullable=True, index=True)
    sub_ward = Column(String(64), nullable=True)
    properties = Column(JSON, nullable=True)
    source = Column(String(128), default="OpenStreetMap / BMC Public GIS")

    study_area = relationship("StudyArea", back_populates="infrastructure_items")


class RoadSegment(Base):
    __tablename__ = "road_segments"

    road_segment_id = Column(String(64), primary_key=True, index=True)
    name = Column(String(255), nullable=True)
    road_class = Column(String(64), nullable=False, index=True)
    geometry = Column(JSON, nullable=False)
    length_meters = Column(Numeric(10, 2), nullable=True)
    speed_kmh = Column(Numeric(5, 1), nullable=True)
    locality_name = Column(String(128), nullable=True, index=True)
    elevation_m = Column(Numeric(6, 2), nullable=True)
    connectivity_attributes = Column(JSON, nullable=True)
    vulnerability_index = Column(Numeric(3, 2), default=0.0)
    source = Column(String(128), default="OpenStreetMap")


class Building(Base):
    __tablename__ = "buildings"

    building_id = Column(String(64), primary_key=True, index=True)
    name = Column(String(255), nullable=True)
    building_type = Column(String(64), nullable=False, default="residential", index=True)
    study_area_id = Column(String(64), ForeignKey("study_areas.study_area_id", ondelete="SET NULL"), nullable=True, index=True)
    locality_name = Column(String(128), nullable=True, index=True)
    geometry = Column(JSON, nullable=False)
    centroid = Column(JSON, nullable=True)
    height_m = Column(Numeric(6, 2), nullable=True)
    levels = Column(Integer, nullable=True)
    ground_elevation_m = Column(Numeric(6, 2), nullable=True)
    vulnerability_index = Column(Numeric(3, 2), default=0.0)
    properties = Column(JSON, nullable=True)
    source = Column(String(128), default="OpenStreetMap")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    study_area = relationship("StudyArea", back_populates="buildings")


class LocalityAlert(Base):
    __tablename__ = "locality_alerts"

    alert_id = Column(String(64), primary_key=True, index=True)
    locality_name = Column(String(128), nullable=False, index=True)
    study_area_id = Column(String(64), ForeignKey("study_areas.study_area_id", ondelete="SET NULL"), nullable=True, index=True)
    severity_level = Column(String(32), nullable=False, index=True)  # GREEN, YELLOW, ORANGE, RED
    headline = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    expected_water_depth_m = Column(Numeric(5, 2), nullable=True)
    onset_timestamp = Column(DateTime(timezone=True), nullable=True)
    expiry_timestamp = Column(DateTime(timezone=True), nullable=True)
    recommended_action = Column(Text, nullable=True)
    source = Column(String(128), default="EIDT Flood Early Warning Engine")
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    study_area = relationship("StudyArea", back_populates="locality_alerts")


class DataProvenanceLog(Base):
    __tablename__ = "data_provenance_logs"

    log_id = Column(String(64), primary_key=True, index=True)
    source_id = Column(String(64), nullable=False, index=True)
    connector_name = Column(String(128), nullable=False)
    retrieval_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(String(64), nullable=False)
    records_ingested = Column(Integer, default=0)
    spatial_extent = Column(JSON, nullable=True)
    checksum = Column(String(128), nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SchemaMigration(Base):
    __tablename__ = "schema_migrations"

    version = Column(String(64), primary_key=True)
    applied_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    description = Column(Text, nullable=True)


class FloodEvent(Base):
    __tablename__ = "flood_events"

    event_id = Column(String(64), primary_key=True, index=True)
    event_name = Column(String(255), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=True)
    peak_rainfall_mm_24h = Column(Numeric(8, 2), nullable=True)
    observed_extent = Column(JSON, nullable=False)
    study_area_id = Column(String(64), ForeignKey("study_areas.study_area_id"), nullable=True)
    source = Column(String(255), nullable=False)
    confidence_notes = Column(Text, nullable=True)

    study_area = relationship("StudyArea", back_populates="flood_events")


class ModelRun(Base):
    __tablename__ = "model_runs"

    model_run_id = Column(String(64), primary_key=True, index=True)
    model_name = Column(String(128), nullable=False)
    model_version = Column(String(32), nullable=False)
    input_dataset_versions = Column(JSON, nullable=False)
    execution_time = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status = Column(String(32), nullable=False)
    evaluation_metadata = Column(JSON, nullable=True)

    scenarios = relationship("Scenario", back_populates="model_run")


class Scenario(Base):
    __tablename__ = "scenarios"

    scenario_id = Column(String(64), primary_key=True, index=True)
    study_area_id = Column(String(64), ForeignKey("study_areas.study_area_id", ondelete="CASCADE"), nullable=False)
    scenario_name = Column(String(255), nullable=False)
    rainfall_total_mm = Column(Numeric(8, 2), nullable=False)
    duration_hours = Column(Numeric(5, 2), nullable=False)
    assumptions = Column(JSON, nullable=False)
    mitigation_features = Column(JSON, nullable=True)
    model_run_id = Column(String(64), ForeignKey("model_runs.model_run_id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    study_area = relationship("StudyArea", back_populates="scenarios")
    model_run = relationship("ModelRun", back_populates="scenarios")
    results = relationship("SimulationResult", back_populates="scenario", cascade="all, delete-orphan")


class SimulationResult(Base):
    __tablename__ = "simulation_results"

    result_id = Column(String(64), primary_key=True, index=True)
    scenario_id = Column(String(64), ForeignKey("scenarios.scenario_id", ondelete="CASCADE"), nullable=False)
    result_type = Column(String(64), nullable=False)
    result_location = Column(String(512), nullable=True)
    summary_metrics = Column(JSON, nullable=False)
    ward_breakdown = Column(JSON, nullable=True)
    uncertainty_metadata = Column(JSON, nullable=True)
    generated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    scenario = relationship("Scenario", back_populates="results")


class WeatherForecast(Base):
    __tablename__ = "weather_forecasts"

    forecast_id = Column(String(64), primary_key=True, index=True)
    study_area_id = Column(String(64), ForeignKey("study_areas.study_area_id", ondelete="CASCADE"), nullable=True, index=True)
    locality_id = Column(String(64), nullable=True)
    issue_time = Column(DateTime(timezone=True), nullable=False, index=True)
    valid_time = Column(DateTime(timezone=True), nullable=False, index=True)
    retrieval_time = Column(DateTime(timezone=True), nullable=False)
    latitude = Column(Numeric(9, 6), nullable=True)
    longitude = Column(Numeric(9, 6), nullable=True)
    precipitation_mm = Column(Numeric(6, 2), nullable=False, default=0.0)
    rain_mm = Column(Numeric(6, 2), nullable=True)
    weather_code = Column(Integer, nullable=True)
    precipitation_probability_pct = Column(Numeric(5, 2), nullable=True)
    source = Column(String(128), nullable=False, default="Open-Meteo", index=True)
    model_name = Column(String(64), default="best_match")
    units = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    study_area = relationship("StudyArea", backref="forecasts")


class FloodHazardAssessment(Base):
    __tablename__ = "flood_hazard_assessments"

    assessment_id = Column(String(64), primary_key=True, index=True)
    study_area_id = Column(String(64), ForeignKey("study_areas.study_area_id", ondelete="CASCADE"), nullable=True, index=True)
    locality_name = Column(String(128), nullable=False, index=True)
    assessment_time = Column(DateTime(timezone=True), nullable=False, index=True)
    valid_start_time = Column(DateTime(timezone=True), nullable=False)
    valid_end_time = Column(DateTime(timezone=True), nullable=False)
    horizon_hours = Column(Integer, default=24)
    forecast_rainfall_24h_mm = Column(Numeric(6, 2), nullable=False, default=0.0)
    forecast_rainfall_peak_1h_mm = Column(Numeric(6, 2), default=0.0)
    antecedent_rainfall_24h_mm = Column(Numeric(6, 2), default=0.0)
    elevation_mean_m = Column(Numeric(6, 2), nullable=True)
    risk_level = Column(String(32), nullable=False, default="LOW", index=True)
    risk_score = Column(Numeric(4, 2), default=0.0)
    contributing_factors = Column(JSON, nullable=True)
    missing_inputs = Column(JSON, nullable=True)
    input_coverage = Column(JSON, nullable=True)
    confidence_status = Column(String(64), nullable=False, default="MODERATE")
    model_version = Column(String(64), nullable=False, default="EIDT-Hazard-v1.0")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    study_area = relationship("StudyArea", backref="hazard_assessments")


class InundationSimulation(Base):
    __tablename__ = "inundation_simulations"

    simulation_id = Column(String(64), primary_key=True, index=True)
    study_area_id = Column(String(64), ForeignKey("study_areas.study_area_id", ondelete="CASCADE"), nullable=True, index=True)
    run_name = Column(String(255), nullable=False)
    model_type = Column(String(64), nullable=False, index=True)
    model_version = Column(String(32), nullable=False, default="EIDT-Inundation-v1.0")
    product_classification = Column(String(64), nullable=False)
    spatial_resolution_m = Column(Numeric(6, 2), default=30.0)
    rainfall_scenario_mm = Column(Numeric(8, 2), nullable=False)
    duration_hours = Column(Numeric(5, 2), default=24.0)
    tide_level_m = Column(Numeric(5, 2), default=4.2)
    soil_saturation_pct = Column(Numeric(5, 2), default=75.0)
    status = Column(String(32), nullable=False, default="COMPLETED", index=True)
    execution_duration_sec = Column(Numeric(8, 2), default=0.0)
    peak_depth_m = Column(Numeric(5, 2), default=0.0)
    mean_depth_m = Column(Numeric(5, 2), default=0.0)
    inundated_area_sq_km = Column(Numeric(10, 4), default=0.0)
    exposed_buildings_count = Column(Integer, default=0)
    exposed_roads_count = Column(Integer, default=0)
    exposed_facilities_count = Column(Integer, default=0)
    exposed_population_est = Column(Integer, default=0)
    depth_distribution = Column(JSON, nullable=True)
    extent_geojson = Column(JSON, nullable=True)
    water_arrival_time_min = Column(Integer, nullable=True)
    input_provenance = Column(JSON, nullable=True)
    uncertainty_metadata = Column(JSON, nullable=True)
    limitation_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    study_area = relationship("StudyArea", backref="inundation_simulations")


class MultiHazardAlert(Base):
    __tablename__ = "multi_hazard_alerts"

    alert_id = Column(String(64), primary_key=True, index=True)
    hazard_type = Column(String(32), nullable=False, index=True)
    geographic_scope = Column(String(128), nullable=False)
    study_area_id = Column(String(64), ForeignKey("study_areas.study_area_id", ondelete="SET NULL"), nullable=True, index=True)
    severity_level = Column(String(32), nullable=False)
    headline = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    rationale = Column(Text, nullable=True)
    lifecycle_status = Column(String(32), nullable=False, default="ISSUED", index=True)
    is_official_warning = Column(Boolean, default=False)
    issuing_authority = Column(String(128), nullable=False)
    onset_timestamp = Column(DateTime(timezone=True), nullable=True)
    expiry_timestamp = Column(DateTime(timezone=True), nullable=True, index=True)
    recommended_action = Column(Text, nullable=True)
    evidence_data = Column(JSON, nullable=True)
    model_version = Column(String(64), nullable=True)
    deduplication_hash = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    study_area = relationship("StudyArea", backref="multi_hazard_alerts")


class HazardAssessment(Base):
    __tablename__ = "hazard_assessments"

    assessment_id = Column(String(64), primary_key=True, index=True)
    hazard_type = Column(String(32), nullable=False, index=True)
    study_area_id = Column(String(64), ForeignKey("study_areas.study_area_id", ondelete="CASCADE"), nullable=False, index=True)
    locality_name = Column(String(128), nullable=False)
    assessment_time = Column(DateTime(timezone=True), nullable=False, index=True)
    valid_start_time = Column(DateTime(timezone=True), nullable=False)
    valid_end_time = Column(DateTime(timezone=True), nullable=False)
    horizon_hours = Column(Integer, default=24)
    risk_category = Column(String(32), nullable=False, default="LOW")
    risk_score = Column(Numeric(4, 2), default=0.0)
    metrics = Column(JSON, nullable=True)
    contributing_factors = Column(JSON, nullable=True)
    missing_inputs = Column(JSON, nullable=True)
    confidence_status = Column(String(64), nullable=False)
    model_version = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    study_area = relationship("StudyArea", backref="hazard_assessments_records")


class EmergencyFacility(Base):
    __tablename__ = "emergency_facilities"

    facility_id = Column(String(64), primary_key=True, index=True)
    source_id = Column(String(64), nullable=True)
    source_name = Column(String(128), nullable=False, default="OpenStreetMap / MCGM Civic Directory")
    name = Column(String(255), nullable=False)
    facility_type = Column(String(64), nullable=False, index=True)  # hospital, fire_station, police_station, evacuation_shelter, relief_centre
    latitude = Column(Numeric(10, 6), nullable=False)
    longitude = Column(Numeric(10, 6), nullable=False)
    locality_name = Column(String(128), nullable=True, index=True)
    ward_id = Column(String(64), ForeignKey("study_areas.study_area_id", ondelete="SET NULL"), nullable=True, index=True)
    verification_status = Column(String(64), nullable=False, default="VERIFIED_MUNICIPAL")  # VERIFIED_MUNICIPAL, VERIFIED_OSM, UNVERIFIED
    last_verified_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    operating_status = Column(String(64), nullable=False, default="OPERATIONAL", index=True)  # OPERATIONAL, UNKNOWN, LIMITED_CAPACITY, CLOSED
    contact_phone = Column(String(64), nullable=True)
    capacity_total = Column(Integer, nullable=True)
    capacity_available = Column(Integer, nullable=True)
    capacity_status_notes = Column(Text, nullable=True)
    is_officially_designated_shelter = Column(Boolean, default=False, index=True)
    accessibility_notes = Column(Text, nullable=True)
    provenance_url = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    study_area = relationship("StudyArea", backref="emergency_facilities")


class RoadRestriction(Base):
    __tablename__ = "road_restrictions"

    restriction_id = Column(String(64), primary_key=True, index=True)
    road_segment_id = Column(String(64), ForeignKey("road_segments.road_segment_id", ondelete="CASCADE"), nullable=True, index=True)
    road_name = Column(String(255), nullable=True)
    restriction_type = Column(String(64), nullable=False, index=True)  # CLOSURE_FLOOD, CLOSURE_LANDSLIDE, POLICE_RESTRICTION, SCENARIO_HYPOTHETICAL
    severity = Column(String(32), nullable=False, default="BLOCKED")  # BLOCKED, PARTIAL_SPEED_REDUCTION, ADVISORY
    is_hypothetical_scenario = Column(Boolean, default=False, index=True)
    scenario_id = Column(String(64), nullable=True, index=True)
    cause_description = Column(Text, nullable=False)
    issuing_authority = Column(String(128), nullable=False)
    valid_from = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    valid_until = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    road_segment = relationship("RoadSegment", backref="restrictions")


class RouteRequest(Base):
    __tablename__ = "route_requests"

    request_id = Column(String(64), primary_key=True, index=True)
    origin_lat = Column(Numeric(10, 6), nullable=False)
    origin_lon = Column(Numeric(10, 6), nullable=False)
    destination_lat = Column(Numeric(10, 6), nullable=False)
    destination_lon = Column(Numeric(10, 6), nullable=False)
    target_facility_id = Column(String(64), ForeignKey("emergency_facilities.facility_id", ondelete="SET NULL"), nullable=True)
    routing_mode = Column(String(64), nullable=False, default="HAZARD_AWARE_SAFE", index=True)
    include_alternatives = Column(Boolean, default=True)
    distance_m = Column(Numeric(10, 2), nullable=True)
    estimated_duration_sec = Column(Numeric(10, 2), nullable=True)
    hazard_exposure_summary = Column(JSON, nullable=True)
    route_geometry = Column(JSON, nullable=True)
    unassessed_segments_count = Column(Integer, default=0)
    data_timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    safety_disclaimer = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    target_facility = relationship("EmergencyFacility", backref="route_requests")


class EvacuationScenario(Base):
    __tablename__ = "evacuation_scenarios"

    scenario_id = Column(String(64), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    target_ward_id = Column(String(64), ForeignKey("study_areas.study_area_id", ondelete="SET NULL"), nullable=True, index=True)
    active_restrictions = Column(JSON, nullable=True)
    flood_depth_threshold_cm = Column(Numeric(5, 1), default=30.0)
    created_by = Column(String(128), default="EIDT Emergency Planner")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    study_area = relationship("StudyArea", backref="evacuation_scenarios")


class SourceHealthRecord(Base):
    __tablename__ = "source_health_records"

    source_id = Column(String(64), primary_key=True)
    source_name = Column(String(128), nullable=False)
    category = Column(String(64), nullable=False)
    health_status = Column(String(32), nullable=False, default="healthy")  # healthy, delayed, stale, unavailable, not_configured, degraded
    freshness_threshold_minutes = Column(Integer, nullable=False, default=180)
    expected_cadence_minutes = Column(Integer, nullable=False, default=60)
    last_successful_retrieval = Column(DateTime(timezone=True), nullable=True)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    consecutive_failures = Column(Integer, default=0)
    error_details = Column(Text, nullable=True)
    records_count = Column(Integer, default=0)
    metrics = Column(JSON, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ScheduledIngestionJob(Base):
    __tablename__ = "scheduled_ingestion_jobs"

    job_id = Column(String(64), primary_key=True)
    job_name = Column(String(64), nullable=False, index=True)
    source_id = Column(String(64), nullable=False, index=True)
    schedule_interval = Column(String(64), nullable=False)
    scheduled_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), nullable=False, index=True)  # SCHEDULED, RUNNING, SUCCESS, PARTIAL_SUCCESS, FAILED, SKIPPED
    records_retrieved = Column(Integer, default=0)
    records_accepted = Column(Integer, default=0)
    records_rejected = Column(Integer, default=0)
    records_deduplicated = Column(Integer, default=0)
    retry_count = Column(Integer, default=0)
    error_category = Column(String(64), nullable=True)
    execution_log = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class IngestedObservation(Base):
    __tablename__ = "ingested_observations"

    observation_id = Column(String(64), primary_key=True)
    source_id = Column(String(64), nullable=False, index=True)
    source_record_id = Column(String(128), nullable=True)
    variable_name = Column(String(64), nullable=False, index=True)
    value = Column(Numeric(10, 4), nullable=False)
    unit = Column(String(32), nullable=False)
    locality_name = Column(String(128), nullable=True, index=True)
    latitude = Column(Numeric(10, 6), nullable=True)
    longitude = Column(Numeric(10, 6), nullable=True)
    spatial_ref = Column(JSON, nullable=True)
    observed_at = Column(DateTime(timezone=True), nullable=True, index=True)
    issued_at = Column(DateTime(timezone=True), nullable=True)
    valid_at = Column(DateTime(timezone=True), nullable=True, index=True)
    retrieved_at = Column(DateTime(timezone=True), nullable=False, index=True)
    processed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    product_version = Column(String(64), nullable=True)
    quality_flags = Column(JSON, nullable=True)
    ingestion_run_id = Column(String(64), nullable=True, index=True)
    provenance_id = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AlertLifecycleEvent(Base):
    __tablename__ = "alert_lifecycle_events"

    event_id = Column(String(64), primary_key=True)
    alert_id = Column(String(64), nullable=False, index=True)
    previous_state = Column(String(32), nullable=True)
    new_state = Column(String(32), nullable=False, index=True)
    transition_reason = Column(Text, nullable=False)
    triggered_by = Column(String(64), default="SYSTEM")
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AlertNotification(Base):
    __tablename__ = "alert_notifications"

    notification_id = Column(String(64), primary_key=True)
    alert_id = Column(String(64), nullable=False, index=True)
    channel = Column(String(32), nullable=False, index=True)  # in_app, email, webhook, sms
    recipient_target = Column(String(128), nullable=False)
    status = Column(String(32), nullable=False, index=True)  # QUEUED, DELIVERED, FAILED, SUPPRESSED
    attempt_count = Column(Integer, default=1)
    payload_summary = Column(Text, nullable=True)
    provider_response = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class HistoricalHazardEvent(Base):
    __tablename__ = "historical_hazard_events"

    event_id = Column(String(64), primary_key=True)
    event_name = Column(String(255), nullable=False)
    hazard_type = Column(String(32), nullable=False, index=True)
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    geographic_scope = Column(String(128), nullable=False)
    affected_localities = Column(JSON, nullable=False)
    primary_source = Column(String(255), nullable=False)
    source_url = Column(Text, nullable=True)
    license = Column(String(128), nullable=True)
    evidence_classification = Column(String(64), nullable=False)
    confidence_flag = Column(String(32), nullable=False, default="HIGH")
    meteorological_metrics = Column(JSON, nullable=True)
    impact_summary = Column(Text, nullable=True)
    retrieved_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class EvaluationDataset(Base):
    __tablename__ = "evaluation_datasets"

    dataset_id = Column(String(64), primary_key=True)
    dataset_name = Column(String(128), nullable=False)
    hazard_type = Column(String(32), nullable=False, index=True)
    version = Column(String(32), nullable=False)
    split_strategy = Column(String(64), nullable=False)
    train_start = Column(DateTime(timezone=True), nullable=True)
    train_end = Column(DateTime(timezone=True), nullable=True)
    test_start = Column(DateTime(timezone=True), nullable=True)
    test_end = Column(DateTime(timezone=True), nullable=True)
    total_samples = Column(Integer, default=0)
    train_samples_count = Column(Integer, default=0)
    test_samples_count = Column(Integer, default=0)
    leakage_controls = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class EvaluationDatasetSample(Base):
    __tablename__ = "evaluation_dataset_samples"

    sample_id = Column(String(64), primary_key=True)
    dataset_id = Column(String(64), ForeignKey("evaluation_datasets.dataset_id", ondelete="CASCADE"), nullable=False, index=True)
    event_id = Column(String(64), ForeignKey("historical_hazard_events.event_id", ondelete="CASCADE"), nullable=False, index=True)
    locality_id = Column(String(64), nullable=False)
    locality_name = Column(String(128), nullable=False)
    prediction_issue_time = Column(DateTime(timezone=True), nullable=False)
    valid_time = Column(DateTime(timezone=True), nullable=False)
    predictors = Column(JSON, nullable=False)
    reference_outcome = Column(Numeric(8, 4), nullable=False)
    reference_source = Column(String(255), nullable=False)
    reference_time = Column(DateTime(timezone=True), nullable=False)
    split_assignment = Column(String(32), nullable=False, index=True)
    quality_flags = Column(JSON, nullable=True)


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    run_id = Column(String(64), primary_key=True)
    model_id = Column(String(64), nullable=False, index=True)
    model_version = Column(String(64), nullable=False)
    dataset_id = Column(String(64), ForeignKey("evaluation_datasets.dataset_id", ondelete="CASCADE"), nullable=False)
    hazard_type = Column(String(32), nullable=False)
    evaluation_type = Column(String(64), nullable=False)
    executed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    sample_size = Column(Integer, nullable=False)
    status = Column(String(32), nullable=False, index=True)
    limitation_notes = Column(Text, nullable=True)


class EvaluationMetric(Base):
    __tablename__ = "evaluation_metrics"

    metric_id = Column(String(64), primary_key=True)
    run_id = Column(String(64), ForeignKey("evaluation_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    metric_name = Column(String(64), nullable=False, index=True)
    metric_value = Column(Numeric(10, 4), nullable=False)
    baseline_value = Column(Numeric(10, 4), nullable=True)
    sample_size = Column(Integer, nullable=False)
    confidence_interval_low = Column(Numeric(10, 4), nullable=True)
    confidence_interval_high = Column(Numeric(10, 4), nullable=True)
    metric_definition = Column(Text, nullable=False)


class HistoricalReplayRun(Base):
    __tablename__ = "historical_replay_runs"

    replay_id = Column(String(64), primary_key=True)
    event_id = Column(String(64), ForeignKey("historical_hazard_events.event_id", ondelete="CASCADE"), nullable=False, index=True)
    replay_name = Column(String(255), nullable=False)
    hazard_type = Column(String(32), nullable=False)
    replay_mode = Column(String(64), nullable=False, index=True)  # RETROSPECTIVE_RECONSTRUCTION, GENUINE_ARCHIVED_VINTAGE, HYPOTHETICAL_SCENARIO
    issue_timestamp = Column(DateTime(timezone=True), nullable=False)
    model_version = Column(String(64), nullable=False)
    input_snapshots = Column(JSON, nullable=False)
    predicted_outcomes = Column(JSON, nullable=False)
    observed_benchmark = Column(JSON, nullable=False)
    concordance_metrics = Column(JSON, nullable=False)
    status = Column(String(32), nullable=False)
    is_isolated_from_live = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ModelCalibrationRun(Base):
    __tablename__ = "model_calibration_runs"

    calibration_id = Column(String(64), primary_key=True)
    model_id = Column(String(64), nullable=False, index=True)
    model_version = Column(String(64), nullable=False)
    method = Column(String(64), nullable=False)
    dataset_id = Column(String(64), ForeignKey("evaluation_datasets.dataset_id"), nullable=True)
    brier_score_before = Column(Numeric(8, 4), nullable=False)
    brier_score_after = Column(Numeric(8, 4), nullable=False)
    reliability_bins = Column(JSON, nullable=False)
    calibrator_artifact_path = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class RegionalIngestionTile(Base):
    __tablename__ = "regional_ingestion_tiles"

    tile_id = Column(String(64), primary_key=True)
    district_id = Column(String(64), nullable=False, index=True)
    min_lat = Column(Numeric(8, 4), nullable=False)
    min_lon = Column(Numeric(8, 4), nullable=False)
    max_lat = Column(Numeric(8, 4), nullable=False)
    max_lon = Column(Numeric(8, 4), nullable=False)
    status = Column(String(32), nullable=False, default="IDLE", index=True)  # IDLE, IN_PROGRESS, COMPLETED, FAILED, RETRYING
    retry_count = Column(Integer, default=0)
    last_ingested_at = Column(DateTime(timezone=True), nullable=True)
    data_hash = Column(String(64), nullable=True)
    records_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ApiMetricLog(Base):
    __tablename__ = "api_metric_logs"

    log_id = Column(String(64), primary_key=True)
    correlation_id = Column(String(64), nullable=False, index=True)
    endpoint = Column(String(255), nullable=False, index=True)
    method = Column(String(16), nullable=False)
    status_code = Column(Integer, nullable=False)
    duration_ms = Column(Numeric(10, 2), nullable=False)
    user_agent = Column(Text, nullable=True)
    client_ip = Column(String(64), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)







