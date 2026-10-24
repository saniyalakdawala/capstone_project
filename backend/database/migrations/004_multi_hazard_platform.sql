-- =========================================================================
-- EIDT Migration 004: Maharashtra Multi-Hazard Platform Schema Extension
-- 1. Table for multi-hazard alert lifecycle (multi_hazard_alerts)
-- 2. Table for standardized multi-hazard locality assessments (hazard_assessments)
-- Idempotent, non-destructive, preserves all existing tables and data.
-- =========================================================================

-- 1. Multi-Hazard Alerts Table
CREATE TABLE IF NOT EXISTS multi_hazard_alerts (
    alert_id VARCHAR(64) PRIMARY KEY,
    hazard_type VARCHAR(32) NOT NULL, -- 'flood', 'heatwave', 'landslide', 'drought', 'coastal', 'thunderstorm'
    geographic_scope VARCHAR(128) NOT NULL,
    study_area_id VARCHAR(64) REFERENCES study_areas(study_area_id) ON DELETE SET NULL,
    severity_level VARCHAR(32) NOT NULL, -- 'ADVISORY', 'WATCH', 'WARNING', 'SEVERE'
    headline VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    rationale TEXT,
    lifecycle_status VARCHAR(32) NOT NULL DEFAULT 'ISSUED', -- 'CANDIDATE', 'VERIFIED', 'ISSUED', 'UPDATED', 'EXPIRED', 'WITHDRAWN'
    is_official_warning BOOLEAN DEFAULT FALSE,
    issuing_authority VARCHAR(128) NOT NULL, -- 'IMD', 'INCOIS', 'GSI', 'CWC', 'EIDT Engine'
    onset_timestamp TIMESTAMP WITH TIME ZONE,
    expiry_timestamp TIMESTAMP WITH TIME ZONE,
    recommended_action TEXT,
    evidence_data JSONB,
    model_version VARCHAR(64),
    deduplication_hash VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_multi_alerts_hazard ON multi_hazard_alerts (hazard_type);
CREATE INDEX IF NOT EXISTS idx_multi_alerts_status ON multi_hazard_alerts (lifecycle_status);
CREATE INDEX IF NOT EXISTS idx_multi_alerts_expiry ON multi_hazard_alerts (expiry_timestamp);
CREATE INDEX IF NOT EXISTS idx_multi_alerts_hash ON multi_hazard_alerts (deduplication_hash);
CREATE INDEX IF NOT EXISTS idx_multi_alerts_study_area ON multi_hazard_alerts (study_area_id);

-- 2. Multi-Hazard Locality Assessments Table
CREATE TABLE IF NOT EXISTS hazard_assessments (
    assessment_id VARCHAR(64) PRIMARY KEY,
    hazard_type VARCHAR(32) NOT NULL,
    study_area_id VARCHAR(64) REFERENCES study_areas(study_area_id) ON DELETE CASCADE,
    locality_name VARCHAR(128) NOT NULL,
    assessment_time TIMESTAMP WITH TIME ZONE NOT NULL,
    valid_start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    valid_end_time TIMESTAMP WITH TIME ZONE NOT NULL,
    horizon_hours INTEGER DEFAULT 24,
    risk_category VARCHAR(32) NOT NULL DEFAULT 'LOW', -- 'LOW', 'MODERATE', 'HIGH', 'VERY_HIGH'
    risk_score NUMERIC(4, 2) DEFAULT 0.0,
    metrics JSONB,
    contributing_factors JSONB,
    missing_inputs JSONB,
    confidence_status VARCHAR(64) NOT NULL,
    model_version VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_hazard_assess_type ON hazard_assessments (hazard_type);
CREATE INDEX IF NOT EXISTS idx_hazard_assess_area ON hazard_assessments (study_area_id);
CREATE INDEX IF NOT EXISTS idx_hazard_assess_time ON hazard_assessments (assessment_time DESC);

-- Record migration version in ledger
INSERT INTO schema_migrations (version, description)
VALUES ('004_multi_hazard_platform', 'Multi-hazard alert lifecycle and cross-hazard locality risk assessment platform')
ON CONFLICT (version) DO NOTHING;
