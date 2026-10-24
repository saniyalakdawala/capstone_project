-- =========================================================================
-- EIDT Migration 002: Flood Hazard Module Schema Extension
-- 1. Table for traceable hourly precipitation forecasts (weather_forecasts)
-- 2. Table for versioned locality flood-hazard assessments (flood_hazard_assessments)
-- Idempotent, safe to rerun, preserves all existing tables and data.
-- =========================================================================

-- 1. Hourly Weather Forecasts Table
CREATE TABLE IF NOT EXISTS weather_forecasts (
    forecast_id VARCHAR(64) PRIMARY KEY,
    study_area_id VARCHAR(64) REFERENCES study_areas(study_area_id) ON DELETE CASCADE,
    locality_id VARCHAR(64),
    issue_time TIMESTAMP WITH TIME ZONE NOT NULL,
    valid_time TIMESTAMP WITH TIME ZONE NOT NULL,
    retrieval_time TIMESTAMP WITH TIME ZONE NOT NULL,
    latitude NUMERIC(9, 6),
    longitude NUMERIC(9, 6),
    precipitation_mm NUMERIC(6, 2) NOT NULL DEFAULT 0.0,
    rain_mm NUMERIC(6, 2),
    weather_code INTEGER,
    precipitation_probability_pct NUMERIC(5, 2),
    source VARCHAR(128) NOT NULL DEFAULT 'Open-Meteo',
    model_name VARCHAR(64) DEFAULT 'best_match',
    units JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_forecasts_valid_time ON weather_forecasts (valid_time);
CREATE INDEX IF NOT EXISTS idx_forecasts_issue_time ON weather_forecasts (issue_time DESC);
CREATE INDEX IF NOT EXISTS idx_forecasts_study_area ON weather_forecasts (study_area_id);
CREATE INDEX IF NOT EXISTS idx_forecasts_source ON weather_forecasts (source);

-- 2. Locality Flood Hazard Assessments Table
CREATE TABLE IF NOT EXISTS flood_hazard_assessments (
    assessment_id VARCHAR(64) PRIMARY KEY,
    study_area_id VARCHAR(64) REFERENCES study_areas(study_area_id) ON DELETE CASCADE,
    locality_name VARCHAR(128) NOT NULL,
    assessment_time TIMESTAMP WITH TIME ZONE NOT NULL,
    valid_start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    valid_end_time TIMESTAMP WITH TIME ZONE NOT NULL,
    horizon_hours INTEGER DEFAULT 24,
    forecast_rainfall_24h_mm NUMERIC(6, 2) NOT NULL DEFAULT 0.0,
    forecast_rainfall_peak_1h_mm NUMERIC(6, 2) DEFAULT 0.0,
    antecedent_rainfall_24h_mm NUMERIC(6, 2) DEFAULT 0.0,
    elevation_mean_m NUMERIC(6, 2),
    risk_level VARCHAR(32) NOT NULL DEFAULT 'LOW',
    risk_score NUMERIC(4, 2) DEFAULT 0.0,
    contributing_factors JSONB,
    missing_inputs JSONB,
    input_coverage JSONB,
    confidence_status VARCHAR(64) NOT NULL DEFAULT 'MODERATE',
    model_version VARCHAR(64) NOT NULL DEFAULT 'EIDT-Hazard-v1.0',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_hazard_study_area ON flood_hazard_assessments (study_area_id);
CREATE INDEX IF NOT EXISTS idx_hazard_risk_level ON flood_hazard_assessments (risk_level);
CREATE INDEX IF NOT EXISTS idx_hazard_time ON flood_hazard_assessments (assessment_time DESC);

-- Record migration version in ledger
INSERT INTO schema_migrations (version, description)
VALUES ('002_flood_hazard_module', 'Traceable hourly forecasts and locality flood-hazard assessments')
ON CONFLICT (version) DO NOTHING;
