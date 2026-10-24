-- Migration 006: Real-Time Monitoring, Automated Ingestion and Alert Orchestration Platform
-- Phase 5: High-reliability monitoring, source health, multi-source ingestion, temporal decoupling, and alert lifecycle.

CREATE TABLE IF NOT EXISTS source_health_records (
    source_id VARCHAR(64) PRIMARY KEY,
    source_name VARCHAR(128) NOT NULL,
    category VARCHAR(64) NOT NULL,
    health_status VARCHAR(32) NOT NULL DEFAULT 'healthy', -- healthy, delayed, stale, unavailable, not_configured, degraded
    freshness_threshold_minutes INTEGER NOT NULL DEFAULT 180,
    expected_cadence_minutes INTEGER NOT NULL DEFAULT 60,
    last_successful_retrieval TIMESTAMP WITH TIME ZONE,
    last_attempt_at TIMESTAMP WITH TIME ZONE,
    consecutive_failures INTEGER DEFAULT 0,
    error_details TEXT,
    records_count INTEGER DEFAULT 0,
    metrics JSONB,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scheduled_ingestion_jobs (
    job_id VARCHAR(64) PRIMARY KEY,
    job_name VARCHAR(64) NOT NULL,
    source_id VARCHAR(64) NOT NULL,
    schedule_interval VARCHAR(64) NOT NULL,
    scheduled_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(32) NOT NULL, -- SCHEDULED, RUNNING, SUCCESS, PARTIAL_SUCCESS, FAILED, SKIPPED
    records_retrieved INTEGER DEFAULT 0,
    records_accepted INTEGER DEFAULT 0,
    records_rejected INTEGER DEFAULT 0,
    records_deduplicated INTEGER DEFAULT 0,
    retry_count INTEGER DEFAULT 0,
    error_category VARCHAR(64),
    execution_log TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sched_jobs_name ON scheduled_ingestion_jobs(job_name);
CREATE INDEX IF NOT EXISTS idx_sched_jobs_source ON scheduled_ingestion_jobs(source_id);
CREATE INDEX IF NOT EXISTS idx_sched_jobs_status ON scheduled_ingestion_jobs(status);
CREATE INDEX IF NOT EXISTS idx_sched_jobs_sched_at ON scheduled_ingestion_jobs(scheduled_at);

CREATE TABLE IF NOT EXISTS ingested_observations (
    observation_id VARCHAR(64) PRIMARY KEY,
    source_id VARCHAR(64) NOT NULL,
    source_record_id VARCHAR(128),
    variable_name VARCHAR(64) NOT NULL, -- precipitation, rain_rate, temperature, humidity, wind_speed, water_level
    value NUMERIC(10, 4) NOT NULL,
    unit VARCHAR(32) NOT NULL,
    locality_name VARCHAR(128),
    latitude NUMERIC(10, 6),
    longitude NUMERIC(10, 6),
    spatial_ref JSONB,
    observed_at TIMESTAMP WITH TIME ZONE, -- measurement actual time
    issued_at TIMESTAMP WITH TIME ZONE,   -- forecast or bulletin issue time
    valid_at TIMESTAMP WITH TIME ZONE,    -- forecast validity timestamp
    retrieved_at TIMESTAMP WITH TIME ZONE NOT NULL, -- EIDT ingestion timestamp
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    product_version VARCHAR(64),
    quality_flags JSONB,
    ingestion_run_id VARCHAR(64),
    provenance_id VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ingested_obs_src ON ingested_observations(source_id);
CREATE INDEX IF NOT EXISTS idx_ingested_obs_var ON ingested_observations(variable_name);
CREATE INDEX IF NOT EXISTS idx_ingested_obs_loc ON ingested_observations(locality_name);
CREATE INDEX IF NOT EXISTS idx_ingested_obs_obs_at ON ingested_observations(observed_at);
CREATE INDEX IF NOT EXISTS idx_ingested_obs_valid_at ON ingested_observations(valid_at);
CREATE INDEX IF NOT EXISTS idx_ingested_obs_ret_at ON ingested_observations(retrieved_at);
CREATE INDEX IF NOT EXISTS idx_ingested_obs_run_id ON ingested_observations(ingestion_run_id);

CREATE TABLE IF NOT EXISTS alert_lifecycle_events (
    event_id VARCHAR(64) PRIMARY KEY,
    alert_id VARCHAR(64) NOT NULL,
    previous_state VARCHAR(32),
    new_state VARCHAR(32) NOT NULL, -- new, active, updated, expired, cancelled, superseded
    transition_reason TEXT NOT NULL,
    triggered_by VARCHAR(64) DEFAULT 'SYSTEM',
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_alert_events_alert ON alert_lifecycle_events(alert_id);
CREATE INDEX IF NOT EXISTS idx_alert_events_state ON alert_lifecycle_events(new_state);

CREATE TABLE IF NOT EXISTS alert_notifications (
    notification_id VARCHAR(64) PRIMARY KEY,
    alert_id VARCHAR(64) NOT NULL,
    channel VARCHAR(32) NOT NULL, -- in_app, email, webhook, sms
    recipient_target VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL, -- QUEUED, DELIVERED, FAILED, SUPPRESSED
    attempt_count INTEGER DEFAULT 1,
    payload_summary TEXT,
    provider_response JSONB,
    error_message TEXT,
    sent_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_alert_notif_alert ON alert_notifications(alert_id);
CREATE INDEX IF NOT EXISTS idx_alert_notif_status ON alert_notifications(status);
CREATE INDEX IF NOT EXISTS idx_alert_notif_chan ON alert_notifications(channel);

-- Record migration version in ledger
INSERT INTO schema_migrations (version, description)
VALUES ('006_monitoring_and_alert_orchestration', 'Real-time monitoring, automated ingestion jobs, observations, alert lifecycle, and notification records')
ON CONFLICT (version) DO NOTHING;

