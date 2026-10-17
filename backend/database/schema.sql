-- =========================================================================
-- EARTH INTELLIGENCE DIGITAL TWIN (EIDT) - MUMBAI FLOOD INTELLIGENCE
-- Comprehensive PostgreSQL / PostGIS Spatial Database Schema
-- Version: 1.0.0
-- Reference: Section 8 & Section 14
-- =========================================================================

-- Optional PostGIS extension activation if available in the PostgreSQL instance
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS postgis;
    RAISE NOTICE 'PostGIS extension initialized or already present.';
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'PostGIS extension not available in environment; using standardized WKT/GeoJSON spatial representations.';
END $$;

-- Drop existing tables in dependency order if recreating
DROP TABLE IF EXISTS simulation_results CASCADE;
DROP TABLE IF EXISTS scenarios CASCADE;
DROP TABLE IF EXISTS model_runs CASCADE;
DROP TABLE IF EXISTS flood_events CASCADE;
DROP TABLE IF EXISTS road_segments CASCADE;
DROP TABLE IF EXISTS infrastructure CASCADE;
DROP TABLE IF EXISTS environmental_features CASCADE;
DROP TABLE IF EXISTS satellite_observations CASCADE;
DROP TABLE IF EXISTS weather_observations CASCADE;
DROP TABLE IF EXISTS study_areas CASCADE;

-- -------------------------------------------------------------------------
-- 1. StudyArea: Administrative & Pilot Geographic Boundaries
-- -------------------------------------------------------------------------
CREATE TABLE study_areas (
    study_area_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    administrative_level VARCHAR(64) NOT NULL DEFAULT 'Ward',
    geometry JSONB NOT NULL,                 -- GeoJSON polygon/multipolygon representation
    bounding_box JSONB,                      -- [minX, minY, maxX, maxY]
    area_sq_km NUMERIC(10, 4),
    population INTEGER,
    elevation_mean_m NUMERIC(6, 2),
    source VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_study_areas_name ON study_areas (name);
CREATE INDEX idx_study_areas_geom ON study_areas USING gin (geometry);

-- -------------------------------------------------------------------------
-- 2. WeatherObservation: In-situ, AWS, and Forecast Rainfall
-- -------------------------------------------------------------------------
CREATE TABLE weather_observations (
    observation_id VARCHAR(64) PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    study_area_id VARCHAR(64) REFERENCES study_areas(study_area_id) ON DELETE CASCADE,
    rainfall_mm NUMERIC(8, 2) NOT NULL,
    temperature_c NUMERIC(5, 2),
    humidity NUMERIC(5, 2),
    wind_speed NUMERIC(5, 2),
    source VARCHAR(128) NOT NULL,            -- e.g. 'IMD Santacruz AWS', 'IMD Colaba AWS', 'NASA GPM'
    observation_type VARCHAR(64) NOT NULL    -- 'observed', 'forecast', 'reanalysis', 'simulated'
);

CREATE INDEX idx_weather_timestamp ON weather_observations (timestamp DESC);
CREATE INDEX idx_weather_study_area ON weather_observations (study_area_id);
CREATE INDEX idx_weather_type ON weather_observations (observation_type);

-- -------------------------------------------------------------------------
-- 3. SatelliteObservation: Sentinel-1 SAR & Sentinel-2 Optical Metadata
-- -------------------------------------------------------------------------
CREATE TABLE satellite_observations (
    observation_id VARCHAR(64) PRIMARY KEY,
    acquisition_time TIMESTAMP WITH TIME ZONE NOT NULL,
    sensor VARCHAR(64) NOT NULL,             -- 'Sentinel-1A C-SAR', 'Sentinel-2B MSI'
    product_identifier VARCHAR(255) NOT NULL,
    footprint JSONB NOT NULL,                -- Footprint polygon GeoJSON
    raster_location VARCHAR(512),            -- Path to COG / GeoTIFF storage
    processing_status VARCHAR(64) NOT NULL,  -- 'raw', 'preprocessed', 'inundation_extracted', 'calibrated'
    source_metadata JSONB                    -- Polarization, orbit direction, resolution
);

CREATE INDEX idx_satellite_acq_time ON satellite_observations (acquisition_time DESC);
CREATE INDEX idx_satellite_sensor ON satellite_observations (sensor);

-- -------------------------------------------------------------------------
-- 4. EnvironmentalFeature: Elevation, Slope, LULC, Drainage, Soil
-- -------------------------------------------------------------------------
CREATE TABLE environmental_features (
    feature_id VARCHAR(64) PRIMARY KEY,
    feature_type VARCHAR(64) NOT NULL,       -- 'DEM_Cell', 'River', 'Drainage_Canal', 'Mangrove_Buffer'
    geometry JSONB NOT NULL,
    elevation NUMERIC(6, 2),                 -- Height in meters above MSL
    land_cover VARCHAR(64),                  -- 'Urban_Builtup', 'Water_Body', 'Mangrove', 'Mudflat', 'Open_Vegetation'
    imperviousness_pct NUMERIC(5, 2),
    slope_degrees NUMERIC(5, 2),
    source VARCHAR(128) NOT NULL,
    observed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_env_features_type ON environmental_features (feature_type);
CREATE INDEX idx_env_features_geom ON environmental_features USING gin (geometry);

-- -------------------------------------------------------------------------
-- 5. Infrastructure: Hospitals, Schools, Fire Stations, Critical Buildings
-- -------------------------------------------------------------------------
CREATE TABLE infrastructure (
    infrastructure_id VARCHAR(64) PRIMARY KEY,
    feature_type VARCHAR(64) NOT NULL,       -- 'hospital', 'school', 'fire_station', 'power_substation', 'transit_hub'
    name VARCHAR(255) NOT NULL,
    geometry JSONB NOT NULL,                 -- GeoJSON Point or Polygon
    latitude NUMERIC(10, 6),
    longitude NUMERIC(10, 6),
    ward_id VARCHAR(64) REFERENCES study_areas(study_area_id),
    properties JSONB,                        -- capacity, bed count, emergency status
    source VARCHAR(128) NOT NULL DEFAULT 'OpenStreetMap / BMC Public GIS'
);

CREATE INDEX idx_infra_type ON infrastructure (feature_type);
CREATE INDEX idx_infra_ward ON infrastructure (ward_id);
CREATE INDEX idx_infra_geom ON infrastructure USING gin (geometry);

-- -------------------------------------------------------------------------
-- 6. RoadSegment: Transport Network for Reachability & Graph Routing
-- -------------------------------------------------------------------------
CREATE TABLE road_segments (
    road_segment_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255),
    road_class VARCHAR(64) NOT NULL,         -- 'motorway', 'primary', 'secondary', 'arterial'
    geometry JSONB NOT NULL,                 -- GeoJSON LineString
    length_meters NUMERIC(10, 2),
    speed_kmh NUMERIC(5, 1),
    connectivity_attributes JSONB,          -- u, v nodes, one_way, bridge, subway
    vulnerability_index NUMERIC(3, 2),       -- 0.0 to 1.0 based on historical flooding
    source VARCHAR(128) NOT NULL DEFAULT 'OpenStreetMap'
);

CREATE INDEX idx_roads_class ON road_segments (road_class);
CREATE INDEX idx_roads_geom ON road_segments USING gin (geometry);

-- -------------------------------------------------------------------------
-- 7. FloodEvent: Documented Historical Inundation Events (Validation Ground Truth)
-- -------------------------------------------------------------------------
CREATE TABLE flood_events (
    event_id VARCHAR(64) PRIMARY KEY,
    event_name VARCHAR(255) NOT NULL,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE,
    peak_rainfall_mm_24h NUMERIC(8, 2),
    observed_extent JSONB NOT NULL,          -- Satellite & Municipal validated flood polygon
    study_area_id VARCHAR(64) REFERENCES study_areas(study_area_id),
    source VARCHAR(255) NOT NULL,            -- e.g. 'BMC Disaster Cell / Dartmouth Flood Observatory'
    confidence_notes TEXT
);

CREATE INDEX idx_flood_events_dates ON flood_events (start_time, end_time);

-- -------------------------------------------------------------------------
-- 8. ModelRun: AI/ML & Hydrological Model Execution Tracking
-- -------------------------------------------------------------------------
CREATE TABLE model_runs (
    model_run_id VARCHAR(64) PRIMARY KEY,
    model_name VARCHAR(128) NOT NULL,        -- 'EIDT_RandomForest_v1', 'EIDT_Hydrological_SCS_CN_v1'
    model_version VARCHAR(32) NOT NULL,
    input_dataset_versions JSONB NOT NULL,
    execution_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(32) NOT NULL,             -- 'COMPLETED', 'RUNNING', 'FAILED'
    evaluation_metadata JSONB                -- ROC-AUC, F1, precision, recall, IoU metrics
);

CREATE INDEX idx_model_runs_name ON model_runs (model_name, model_version);

-- -------------------------------------------------------------------------
-- 9. Scenario: Hypothetical Rainfall and Mitigation Planning Configurations
-- -------------------------------------------------------------------------
CREATE TABLE scenarios (
    scenario_id VARCHAR(64) PRIMARY KEY,
    study_area_id VARCHAR(64) REFERENCES study_areas(study_area_id) ON DELETE CASCADE,
    scenario_name VARCHAR(255) NOT NULL,
    rainfall_total_mm NUMERIC(8, 2) NOT NULL,
    duration_hours NUMERIC(5, 2) NOT NULL,
    assumptions JSONB NOT NULL,              -- soil saturation, drainage pumping rate, tide level
    mitigation_features JSONB,               -- retention basins, desilting factor
    model_run_id VARCHAR(64) REFERENCES model_runs(model_run_id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_scenarios_study_area ON scenarios (study_area_id);
CREATE INDEX idx_scenarios_created ON scenarios (created_at DESC);

-- -------------------------------------------------------------------------
-- 10. SimulationResult: Calculated Spatial Risk, Exposure & Graph Impacts
-- -------------------------------------------------------------------------
CREATE TABLE simulation_results (
    result_id VARCHAR(64) PRIMARY KEY,
    scenario_id VARCHAR(64) REFERENCES scenarios(scenario_id) ON DELETE CASCADE,
    result_type VARCHAR(64) NOT NULL,        -- 'flood_extent', 'risk_raster', 'network_accessibility'
    result_location VARCHAR(512),            -- Path to artifact or GeoJSON reference
    summary_metrics JSONB NOT NULL,          -- high_risk_area_sqkm, exposed_pop, affected_roads_count
    ward_breakdown JSONB,                    -- per-ward statistics
    uncertainty_metadata JSONB,              -- epistemic uncertainty, confidence intervals
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sim_results_scenario ON simulation_results (scenario_id);
CREATE INDEX idx_sim_results_type ON simulation_results (result_type);

-- =========================================================================
-- BENCHMARK & DEMONSTRATION GIS-AWARE SQL QUERIES (Section 14 Deliverable)
-- =========================================================================

-- Query A: Identify Critical Hospitals in Flood Zones for a Specific Scenario
-- EXPLAIN ANALYZE
-- SELECT h.infrastructure_id, h.name, h.feature_type, s.scenario_name,
--        r.summary_metrics->>'high_risk_area_sqkm' AS scenario_flooded_km2
-- FROM infrastructure h
-- JOIN study_areas w ON h.ward_id = w.study_area_id
-- JOIN scenarios s ON s.study_area_id = w.study_area_id
-- JOIN simulation_results r ON r.scenario_id = s.scenario_id
-- WHERE h.feature_type = 'hospital' AND s.scenario_id = 'SCEN_EXTREME_300MM';

-- Query B: Calculate Aggregate Exposed Population by Ward
-- SELECT sa.name AS ward_name, sa.population AS total_population,
--        COALESCE((sr.ward_breakdown->sa.study_area_id->>'exposed_pop')::NUMERIC, 0) AS estimated_exposed_population,
--        ROUND(((sr.ward_breakdown->sa.study_area_id->>'exposed_pop')::NUMERIC / sa.population * 100), 2) AS exposure_percentage
-- FROM study_areas sa
-- JOIN simulation_results sr ON sr.result_type = 'exposure_summary'
-- WHERE sr.scenario_id = 'SCEN_HEAVY_200MM'
-- ORDER BY exposure_percentage DESC;

-- Query C: Retrieve Inundated Road Segments and Isolated Hospital Facilities
-- SELECT r.road_segment_id, r.name, r.road_class, r.vulnerability_index
-- FROM road_segments r
-- WHERE r.vulnerability_index >= 0.70;
