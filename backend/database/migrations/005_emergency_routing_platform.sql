-- EIDT Phase 4 Migration: Emergency Response, Evacuation Routing & Decision Support
-- Supports PostgreSQL with JSONB and SQLite compatibility.
-- Additive and non-destructive.

-- 1. Emergency Facilities & Officially Designated Shelters
CREATE TABLE IF NOT EXISTS emergency_facilities (
    facility_id VARCHAR(64) PRIMARY KEY,
    source_id VARCHAR(64),
    source_name VARCHAR(128) NOT NULL DEFAULT 'OpenStreetMap / MCGM Civic Directory',
    name VARCHAR(255) NOT NULL,
    facility_type VARCHAR(64) NOT NULL, -- hospital, fire_station, police_station, evacuation_shelter, relief_centre
    latitude NUMERIC(10, 6) NOT NULL,
    longitude NUMERIC(10, 6) NOT NULL,
    locality_name VARCHAR(128),
    ward_id VARCHAR(64) REFERENCES study_areas(study_area_id) ON DELETE SET NULL,
    verification_status VARCHAR(64) NOT NULL DEFAULT 'VERIFIED_MUNICIPAL', -- VERIFIED_MUNICIPAL, VERIFIED_OSM, UNVERIFIED
    last_verified_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    operating_status VARCHAR(64) NOT NULL DEFAULT 'OPERATIONAL', -- OPERATIONAL, UNKNOWN, LIMITED_CAPACITY, CLOSED
    contact_phone VARCHAR(64),
    capacity_total INTEGER,
    capacity_available INTEGER,
    capacity_status_notes TEXT,
    is_officially_designated_shelter BOOLEAN DEFAULT FALSE,
    accessibility_notes TEXT,
    provenance_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_emergency_facilities_type ON emergency_facilities(facility_type);
CREATE INDEX IF NOT EXISTS idx_emergency_facilities_ward ON emergency_facilities(ward_id);
CREATE INDEX IF NOT EXISTS idx_emergency_facilities_shelter ON emergency_facilities(is_officially_designated_shelter);
CREATE INDEX IF NOT EXISTS idx_emergency_facilities_status ON emergency_facilities(operating_status);

-- 2. Verified Road Closures, Inundation Cut-Offs & Active Routing Restrictions
CREATE TABLE IF NOT EXISTS road_restrictions (
    restriction_id VARCHAR(64) PRIMARY KEY,
    road_segment_id VARCHAR(64) REFERENCES road_segments(road_segment_id) ON DELETE CASCADE,
    road_name VARCHAR(255),
    restriction_type VARCHAR(64) NOT NULL, -- CLOSURE_FLOOD, CLOSURE_LANDSLIDE, POLICE_RESTRICTION, SCENARIO_HYPOTHETICAL
    severity VARCHAR(32) NOT NULL DEFAULT 'BLOCKED', -- BLOCKED, PARTIAL_SPEED_REDUCTION, ADVISORY
    is_hypothetical_scenario BOOLEAN DEFAULT FALSE,
    scenario_id VARCHAR(64),
    cause_description TEXT NOT NULL,
    issuing_authority VARCHAR(128) NOT NULL,
    valid_from TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valid_until TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_road_restrictions_segment ON road_restrictions(road_segment_id);
CREATE INDEX IF NOT EXISTS idx_road_restrictions_active ON road_restrictions(is_active);
CREATE INDEX IF NOT EXISTS idx_road_restrictions_scenario ON road_restrictions(is_hypothetical_scenario);

-- 3. Traceable Route Requests & Calculated Multi-Criteria Paths
CREATE TABLE IF NOT EXISTS route_requests (
    request_id VARCHAR(64) PRIMARY KEY,
    origin_lat NUMERIC(10, 6) NOT NULL,
    origin_lon NUMERIC(10, 6) NOT NULL,
    destination_lat NUMERIC(10, 6) NOT NULL,
    destination_lon NUMERIC(10, 6) NOT NULL,
    target_facility_id VARCHAR(64) REFERENCES emergency_facilities(facility_id) ON DELETE SET NULL,
    routing_mode VARCHAR(64) NOT NULL, -- SHORTEST_DISTANCE, FASTEST_TIME, HAZARD_AWARE_SAFE, SCENARIO_TEST
    include_alternatives BOOLEAN DEFAULT TRUE,
    distance_m NUMERIC(10, 2),
    estimated_duration_sec NUMERIC(10, 2),
    hazard_exposure_summary JSONB,
    route_geometry JSONB,
    unassessed_segments_count INTEGER DEFAULT 0,
    data_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    safety_disclaimer TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_route_requests_created ON route_requests(created_at);
CREATE INDEX IF NOT EXISTS idx_route_requests_mode ON route_requests(routing_mode);

-- 4. Evacuation Planning Scenarios
CREATE TABLE IF NOT EXISTS evacuation_scenarios (
    scenario_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    target_ward_id VARCHAR(64) REFERENCES study_areas(study_area_id) ON DELETE SET NULL,
    active_restrictions JSONB,
    flood_depth_threshold_cm NUMERIC(5, 1) DEFAULT 30.0,
    created_by VARCHAR(128) DEFAULT 'EIDT Emergency Planner',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_evacuation_scenarios_ward ON evacuation_scenarios(target_ward_id);

-- Record migration version in ledger
INSERT INTO schema_migrations (version, description)
VALUES ('005_emergency_routing_platform', 'Emergency facilities, shelters, road restrictions, and evacuation routing platform')
ON CONFLICT (version) DO NOTHING;
