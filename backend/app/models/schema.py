from sqlalchemy import Column, String, Integer, Float, Numeric, DateTime, JSON, Text, ForeignKey
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

    weather_observations = relationship("WeatherObservation", back_populates="study_area", cascade="all, delete-orphan")
    scenarios = relationship("Scenario", back_populates="study_area", cascade="all, delete-orphan")
    infrastructure_items = relationship("Infrastructure", back_populates="study_area")
    flood_events = relationship("FloodEvent", back_populates="study_area")


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
    connectivity_attributes = Column(JSON, nullable=True)
    vulnerability_index = Column(Numeric(3, 2), default=0.0)
    source = Column(String(128), default="OpenStreetMap")


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
