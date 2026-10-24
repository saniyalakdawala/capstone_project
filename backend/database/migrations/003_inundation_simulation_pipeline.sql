-- =========================================================================
-- EIDT Migration 003: Flood Inundation, Water Depth & Impact Simulation Schema Extension
-- 1. Table for versioned, reproducible flood inundation simulations (inundation_simulations)
-- 2. Records spatial extents, depth quantiles, asset exposures, and physical provenance
-- Idempotent, safe to rerun, preserves all existing tables and data.
-- =========================================================================

CREATE TABLE IF NOT EXISTS inundation_simulations (
    simulation_id VARCHAR(64) PRIMARY KEY,
    study_area_id VARCHAR(64) REFERENCES study_areas(study_area_id) ON DELETE CASCADE,
    run_name VARCHAR(255) NOT NULL,
    model_type VARCHAR(64) NOT NULL,
    model_version VARCHAR(32) NOT NULL DEFAULT 'EIDT-Inundation-v1.0',
    product_classification VARCHAR(64) NOT NULL,
    spatial_resolution_m NUMERIC(6, 2) DEFAULT 30.0,
    rainfall_scenario_mm NUMERIC(8, 2) NOT NULL,
    duration_hours NUMERIC(5, 2) DEFAULT 24.0,
    tide_level_m NUMERIC(5, 2) DEFAULT 4.2,
    soil_saturation_pct NUMERIC(5, 2) DEFAULT 75.0,
    status VARCHAR(32) NOT NULL DEFAULT 'COMPLETED',
    execution_duration_sec NUMERIC(8, 2) DEFAULT 0.0,
    peak_depth_m NUMERIC(5, 2) DEFAULT 0.0,
    mean_depth_m NUMERIC(5, 2) DEFAULT 0.0,
    inundated_area_sq_km NUMERIC(10, 4) DEFAULT 0.0,
    exposed_buildings_count INTEGER DEFAULT 0,
    exposed_roads_count INTEGER DEFAULT 0,
    exposed_facilities_count INTEGER DEFAULT 0,
    exposed_population_est INTEGER DEFAULT 0,
    depth_distribution JSONB,
    extent_geojson JSONB,
    water_arrival_time_min INTEGER,
    input_provenance JSONB,
    uncertainty_metadata JSONB,
    limitation_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_inundation_study_area ON inundation_simulations (study_area_id);
CREATE INDEX IF NOT EXISTS idx_inundation_status ON inundation_simulations (status);
CREATE INDEX IF NOT EXISTS idx_inundation_created ON inundation_simulations (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_inundation_model_type ON inundation_simulations (model_type);

-- Record migration version in ledger
INSERT INTO schema_migrations (version, description)
VALUES ('003_inundation_simulation_pipeline', 'Physically defensible flood inundation, water depth, and impact simulation pipeline')
ON CONFLICT (version) DO NOTHING;
