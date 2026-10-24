-- =========================================================================
-- EIDT Migration 001: Regional MMR Foundation Schema Upgrade
-- Idempotent and backward-compatible migration for:
-- 1. Regional administrative hierarchy (parent_region_id, region_type, hierarchy_path)
-- 2. Locality identifiers in infrastructure & road segments
-- 3. Building footprints table (buildings)
-- 4. Future flood warning alert records table (locality_alerts)
-- 5. Data provenance audit logs table (data_provenance_logs)
-- =========================================================================

-- Migration tracking table
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(64) PRIMARY KEY,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

-- 1. Regional Administrative Hierarchy (study_areas)
ALTER TABLE study_areas ADD COLUMN IF NOT EXISTS parent_region_id VARCHAR(64) REFERENCES study_areas(study_area_id) ON DELETE SET NULL;
ALTER TABLE study_areas ADD COLUMN IF NOT EXISTS region_type VARCHAR(64) DEFAULT 'Ward';
ALTER TABLE study_areas ADD COLUMN IF NOT EXISTS hierarchy_path VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_study_areas_parent ON study_areas (parent_region_id);
CREATE INDEX IF NOT EXISTS idx_study_areas_region_type ON study_areas (region_type);

-- 2. Locality Identifiers in Infrastructure
ALTER TABLE infrastructure ADD COLUMN IF NOT EXISTS locality_name VARCHAR(128);
ALTER TABLE infrastructure ADD COLUMN IF NOT EXISTS sub_ward VARCHAR(64);

CREATE INDEX IF NOT EXISTS idx_infra_locality ON infrastructure (locality_name);
CREATE INDEX IF NOT EXISTS idx_infra_sub_ward ON infrastructure (sub_ward);

-- 3. Locality Identifiers and Elevation in Road Segments
ALTER TABLE road_segments ADD COLUMN IF NOT EXISTS locality_name VARCHAR(128);
ALTER TABLE road_segments ADD COLUMN IF NOT EXISTS elevation_m NUMERIC(6, 2);

CREATE INDEX IF NOT EXISTS idx_roads_locality ON road_segments (locality_name);

-- 4. Building Footprints Table
CREATE TABLE IF NOT EXISTS buildings (
    building_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255),
    building_type VARCHAR(64) NOT NULL DEFAULT 'residential',
    study_area_id VARCHAR(64) REFERENCES study_areas(study_area_id) ON DELETE SET NULL,
    locality_name VARCHAR(128),
    geometry JSONB NOT NULL,
    centroid JSONB,
    height_m NUMERIC(6, 2),
    levels INTEGER,
    ground_elevation_m NUMERIC(6, 2),
    vulnerability_index NUMERIC(3, 2) DEFAULT 0.0,
    properties JSONB,
    source VARCHAR(128) DEFAULT 'OpenStreetMap',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_buildings_study_area ON buildings (study_area_id);
CREATE INDEX IF NOT EXISTS idx_buildings_type ON buildings (building_type);
CREATE INDEX IF NOT EXISTS idx_buildings_locality ON buildings (locality_name);
CREATE INDEX IF NOT EXISTS idx_buildings_geom ON buildings USING gin (geometry);

-- 5. Locality Early Warning Alert Records Table
CREATE TABLE IF NOT EXISTS locality_alerts (
    alert_id VARCHAR(64) PRIMARY KEY,
    locality_name VARCHAR(128) NOT NULL,
    study_area_id VARCHAR(64) REFERENCES study_areas(study_area_id) ON DELETE SET NULL,
    severity_level VARCHAR(32) NOT NULL,
    headline VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    expected_water_depth_m NUMERIC(5, 2),
    onset_timestamp TIMESTAMP WITH TIME ZONE,
    expiry_timestamp TIMESTAMP WITH TIME ZONE,
    recommended_action TEXT,
    source VARCHAR(128) DEFAULT 'EIDT Flood Early Warning Engine',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_alerts_locality ON locality_alerts (locality_name);
CREATE INDEX IF NOT EXISTS idx_alerts_study_area ON locality_alerts (study_area_id);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON locality_alerts (severity_level);
CREATE INDEX IF NOT EXISTS idx_alerts_active ON locality_alerts (is_active);

-- 6. Data Provenance Audit Logs Table
CREATE TABLE IF NOT EXISTS data_provenance_logs (
    log_id VARCHAR(64) PRIMARY KEY,
    source_id VARCHAR(64) NOT NULL,
    connector_name VARCHAR(128) NOT NULL,
    retrieval_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    status VARCHAR(64) NOT NULL,
    records_ingested INTEGER DEFAULT 0,
    spatial_extent JSONB,
    checksum VARCHAR(128),
    details TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_prov_source ON data_provenance_logs (source_id);
CREATE INDEX IF NOT EXISTS idx_prov_timestamp ON data_provenance_logs (retrieval_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_prov_status ON data_provenance_logs (status);

-- Record migration version
INSERT INTO schema_migrations (version, description)
VALUES ('001_regional_mmr_foundation', 'Regional administrative hierarchy, locality columns, buildings, locality_alerts, data_provenance_logs')
ON CONFLICT (version) DO NOTHING;
