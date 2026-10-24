-- =========================================================================
-- Migration 008: Maharashtra-Wide Scaling, Hierarchy & Performance Optimization
-- Earth Intelligence Digital Twin (EIDT) - Maharashtra
-- =========================================================================

-- 1. Enhance study_areas table with hierarchy and spatial scaling attributes
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'study_areas' AND column_name = 'aliases') THEN
        ALTER TABLE study_areas ADD COLUMN aliases JSONB DEFAULT '[]'::jsonb;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'study_areas' AND column_name = 'division_id') THEN
        ALTER TABLE study_areas ADD COLUMN division_id VARCHAR(64) NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'study_areas' AND column_name = 'district_id') THEN
        ALTER TABLE study_areas ADD COLUMN district_id VARCHAR(64) NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'study_areas' AND column_name = 'crs') THEN
        ALTER TABLE study_areas ADD COLUMN crs VARCHAR(32) DEFAULT 'EPSG:4326';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'study_areas' AND column_name = 'boundary_version') THEN
        ALTER TABLE study_areas ADD COLUMN boundary_version VARCHAR(64) DEFAULT 'SurveyOfIndia-Census2011/MRSAC-v2.1';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'study_areas' AND column_name = 'effective_date') THEN
        ALTER TABLE study_areas ADD COLUMN effective_date TIMESTAMPTZ DEFAULT NOW();
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'study_areas' AND column_name = 'is_verified') THEN
        ALTER TABLE study_areas ADD COLUMN is_verified BOOLEAN DEFAULT TRUE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'study_areas' AND column_name = 'simplified_geometry') THEN
        ALTER TABLE study_areas ADD COLUMN simplified_geometry JSONB NULL;
    END IF;
END $$;

-- 2. Regional Ingestion Spatial Tiles Table (Phase 7C: Tiled Ingestion & Checkpointing)
CREATE TABLE IF NOT EXISTS regional_ingestion_tiles (
    tile_id VARCHAR(64) PRIMARY KEY,
    district_id VARCHAR(64) NOT NULL,
    min_lat NUMERIC(8,4) NOT NULL,
    min_lon NUMERIC(8,4) NOT NULL,
    max_lat NUMERIC(8,4) NOT NULL,
    max_lon NUMERIC(8,4) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'IDLE',  -- IDLE, IN_PROGRESS, COMPLETED, FAILED, RETRYING
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_ingested_at TIMESTAMPTZ NULL,
    data_hash VARCHAR(64) NULL,
    records_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. API Observability & Latency Metric Log Table (Phase 7I)
CREATE TABLE IF NOT EXISTS api_metric_logs (
    log_id VARCHAR(64) PRIMARY KEY,
    correlation_id VARCHAR(64) NOT NULL,
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(16) NOT NULL,
    status_code INTEGER NOT NULL,
    duration_ms NUMERIC(10,2) NOT NULL,
    user_agent TEXT NULL,
    client_ip VARCHAR(64) NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. High-Performance Composite B-Tree Indexes (Phase 7D: Database Performance)
CREATE INDEX IF NOT EXISTS idx_study_areas_type_parent ON study_areas (region_type, parent_region_id);
CREATE INDEX IF NOT EXISTS idx_study_areas_hierarchy ON study_areas (hierarchy_path);
CREATE INDEX IF NOT EXISTS idx_study_areas_district ON study_areas (district_id);
CREATE INDEX IF NOT EXISTS idx_study_areas_division ON study_areas (division_id);

CREATE INDEX IF NOT EXISTS idx_weather_obs_time_area ON weather_observations (timestamp DESC, study_area_id);
CREATE INDEX IF NOT EXISTS idx_infra_ward_fac ON infrastructure (ward_id, feature_type);
CREATE INDEX IF NOT EXISTS idx_road_loc_class ON road_segments (locality_name, road_class);

CREATE INDEX IF NOT EXISTS idx_hazard_alerts_active_scope ON multi_hazard_alerts (lifecycle_status, geographic_scope, severity_level);
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_status_src ON scheduled_ingestion_jobs (status, source_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_regional_tiles_dist_status ON regional_ingestion_tiles (district_id, status);
CREATE INDEX IF NOT EXISTS idx_api_metrics_time_endpoint ON api_metric_logs (timestamp DESC, endpoint);
CREATE INDEX IF NOT EXISTS idx_api_metrics_correlation ON api_metric_logs (correlation_id);

-- 5. Record migration 008 in schema_migrations ledger
INSERT INTO schema_migrations (version, description)
VALUES (
    '008_maharashtra_wide_scaling',
    'Maharashtra statewide administrative hierarchy, regional tiled ingestion, performance indexes, and observability logs'
)
ON CONFLICT (version) DO NOTHING;
