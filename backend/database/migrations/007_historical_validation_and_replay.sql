-- Migration 007: Historical Disaster Replay, Model Calibration, and Scientific Validation Platform
-- Phase 6: Provenance-aware historical disaster catalogue, leakage-resistant evaluation datasets,
-- probability calibration records, and isolated historical replay engine.

CREATE TABLE IF NOT EXISTS historical_hazard_events (
    event_id VARCHAR(64) PRIMARY KEY,
    event_name VARCHAR(255) NOT NULL,
    hazard_type VARCHAR(32) NOT NULL,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE,
    geographic_scope VARCHAR(128) NOT NULL,
    affected_localities JSONB NOT NULL,
    primary_source VARCHAR(255) NOT NULL,
    source_url TEXT,
    license VARCHAR(128),
    evidence_classification VARCHAR(64) NOT NULL, -- SURVEYED_DISASTER_RECORDS, CIVIC_INCIDENT_LOGS, SATELLITE_SAR_WATER_INDEX, AWS_METEOROLOGICAL_RECORDS
    confidence_flag VARCHAR(32) NOT NULL DEFAULT 'HIGH',
    meteorological_metrics JSONB,
    impact_summary TEXT,
    retrieved_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_hist_events_type ON historical_hazard_events(hazard_type);
CREATE INDEX IF NOT EXISTS idx_hist_events_start ON historical_hazard_events(start_time);

CREATE TABLE IF NOT EXISTS evaluation_datasets (
    dataset_id VARCHAR(64) PRIMARY KEY,
    dataset_name VARCHAR(128) NOT NULL,
    hazard_type VARCHAR(32) NOT NULL,
    version VARCHAR(32) NOT NULL,
    split_strategy VARCHAR(64) NOT NULL, -- TEMPORAL_HOLD_OUT, SPATIAL_HOLD_OUT, EVENT_GROUP_KFOLD
    train_start TIMESTAMP WITH TIME ZONE,
    train_end TIMESTAMP WITH TIME ZONE,
    test_start TIMESTAMP WITH TIME ZONE,
    test_end TIMESTAMP WITH TIME ZONE,
    total_samples INTEGER DEFAULT 0,
    train_samples_count INTEGER DEFAULT 0,
    test_samples_count INTEGER DEFAULT 0,
    leakage_controls JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_eval_ds_hazard ON evaluation_datasets(hazard_type);

CREATE TABLE IF NOT EXISTS evaluation_dataset_samples (
    sample_id VARCHAR(64) PRIMARY KEY,
    dataset_id VARCHAR(64) REFERENCES evaluation_datasets(dataset_id) ON DELETE CASCADE,
    event_id VARCHAR(64) REFERENCES historical_hazard_events(event_id) ON DELETE CASCADE,
    locality_id VARCHAR(64) NOT NULL,
    locality_name VARCHAR(128) NOT NULL,
    prediction_issue_time TIMESTAMP WITH TIME ZONE NOT NULL,
    valid_time TIMESTAMP WITH TIME ZONE NOT NULL,
    predictors JSONB NOT NULL,
    reference_outcome NUMERIC(8, 4) NOT NULL,
    reference_source VARCHAR(255) NOT NULL,
    reference_time TIMESTAMP WITH TIME ZONE NOT NULL,
    split_assignment VARCHAR(32) NOT NULL, -- TRAIN, VALIDATION, TEST
    quality_flags JSONB
);

CREATE INDEX IF NOT EXISTS idx_eval_samples_ds ON evaluation_dataset_samples(dataset_id);
CREATE INDEX IF NOT EXISTS idx_eval_samples_event ON evaluation_dataset_samples(event_id);
CREATE INDEX IF NOT EXISTS idx_eval_samples_split ON evaluation_dataset_samples(split_assignment);

CREATE TABLE IF NOT EXISTS evaluation_runs (
    run_id VARCHAR(64) PRIMARY KEY,
    model_id VARCHAR(64) NOT NULL,
    model_version VARCHAR(64) NOT NULL,
    dataset_id VARCHAR(64) REFERENCES evaluation_datasets(dataset_id) ON DELETE CASCADE,
    hazard_type VARCHAR(32) NOT NULL,
    evaluation_type VARCHAR(64) NOT NULL, -- INDEPENDENT_TEST_SET, CROSS_VALIDATION, EXPLORATORY
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    sample_size INTEGER NOT NULL,
    status VARCHAR(32) NOT NULL, -- COMPLETED, INSUFFICIENT_DATA, FAILED
    limitation_notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_eval_runs_model ON evaluation_runs(model_id);
CREATE INDEX IF NOT EXISTS idx_eval_runs_status ON evaluation_runs(status);

CREATE TABLE IF NOT EXISTS evaluation_metrics (
    metric_id VARCHAR(64) PRIMARY KEY,
    run_id VARCHAR(64) REFERENCES evaluation_runs(run_id) ON DELETE CASCADE,
    metric_name VARCHAR(64) NOT NULL, -- ROC_AUC, PR_AUC, F1, PRECISION, RECALL, CSI, POD, FAR, BRIER_SCORE, IOU, MAE, RMSE
    metric_value NUMERIC(10, 4) NOT NULL,
    baseline_value NUMERIC(10, 4),
    sample_size INTEGER NOT NULL,
    confidence_interval_low NUMERIC(10, 4),
    confidence_interval_high NUMERIC(10, 4),
    metric_definition TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_eval_metrics_run ON evaluation_metrics(run_id);
CREATE INDEX IF NOT EXISTS idx_eval_metrics_name ON evaluation_metrics(metric_name);

CREATE TABLE IF NOT EXISTS historical_replay_runs (
    replay_id VARCHAR(64) PRIMARY KEY,
    event_id VARCHAR(64) REFERENCES historical_hazard_events(event_id) ON DELETE CASCADE,
    replay_name VARCHAR(255) NOT NULL,
    hazard_type VARCHAR(32) NOT NULL,
    replay_mode VARCHAR(64) NOT NULL, -- RETROSPECTIVE_RECONSTRUCTION, GENUINE_ARCHIVED_VINTAGE, HYPOTHETICAL_SCENARIO
    issue_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    model_version VARCHAR(64) NOT NULL,
    input_snapshots JSONB NOT NULL,
    predicted_outcomes JSONB NOT NULL,
    observed_benchmark JSONB NOT NULL,
    concordance_metrics JSONB NOT NULL, -- CSI, Accuracy, Confusion Matrix
    status VARCHAR(32) NOT NULL,
    is_isolated_from_live BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_replay_runs_event ON historical_replay_runs(event_id);
CREATE INDEX IF NOT EXISTS idx_replay_runs_mode ON historical_replay_runs(replay_mode);

CREATE TABLE IF NOT EXISTS model_calibration_runs (
    calibration_id VARCHAR(64) PRIMARY KEY,
    model_id VARCHAR(64) NOT NULL,
    model_version VARCHAR(64) NOT NULL,
    method VARCHAR(64) NOT NULL, -- PLATT_SIGMOID, ISOTONIC_REGRESSION
    dataset_id VARCHAR(64) REFERENCES evaluation_datasets(dataset_id),
    brier_score_before NUMERIC(8, 4) NOT NULL,
    brier_score_after NUMERIC(8, 4) NOT NULL,
    reliability_bins JSONB NOT NULL,
    calibrator_artifact_path TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_model_calib_model ON model_calibration_runs(model_id);

-- Record migration version in ledger
INSERT INTO schema_migrations (version, description)
VALUES ('007_historical_validation_and_replay', 'Historical disaster event catalogue, evaluation datasets, probability calibration, and replay engine')
ON CONFLICT (version) DO NOTHING;
