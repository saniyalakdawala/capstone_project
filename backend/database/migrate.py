"""
Database Migration Runner for Earth Intelligence Digital Twin (EIDT)
Supports PostgreSQL with fallback SQLite support.
Idempotent, non-destructive, and tracks applied migrations in schema_migrations.
"""
import os
import sys
import glob
import logging
import argparse
from datetime import datetime, timezone

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")

def get_connection():
    """Returns a connection to PostgreSQL if available, else SQLite."""
    try:
        import psycopg2
        conn = psycopg2.connect(
            settings.DATABASE_URL,
            connect_timeout=5
        )
        conn.autocommit = False
        return conn, "postgresql"
    except Exception as e:
        logger.warning(f"Could not connect to PostgreSQL ({e}). Using SQLite fallback.")
        import sqlite3
        sqlite_path = os.path.join(backend_dir, "eidt_mumbai.db")
        conn = sqlite3.connect(sqlite_path)
        return conn, "sqlite"

def ensure_migration_table(conn, dialect: str):
    cur = conn.cursor()
    if dialect == "postgresql":
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(64) PRIMARY KEY,
                applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                description TEXT
            );
        """)
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT DEFAULT CURRENT_TIMESTAMP,
                description TEXT
            );
        """)
    conn.commit()
    cur.close()

def get_applied_migrations(conn) -> set:
    cur = conn.cursor()
    cur.execute("SELECT version FROM schema_migrations ORDER BY version")
    applied = {row[0] for row in cur.fetchall()}
    cur.close()
    return applied

def run_sqlite_migration(conn, version: str):
    """Applies migration to SQLite with compatibility translations."""
    cur = conn.cursor()
    
    if version == "001_regional_mmr_foundation":
        # 1. Study areas columns
        cur.execute("PRAGMA table_info(study_areas)")
        sa_cols = [c[1] for c in cur.fetchall()]
        if "parent_region_id" not in sa_cols:
            cur.execute("ALTER TABLE study_areas ADD COLUMN parent_region_id TEXT")
        if "region_type" not in sa_cols:
            cur.execute("ALTER TABLE study_areas ADD COLUMN region_type TEXT DEFAULT 'Ward'")
        if "hierarchy_path" not in sa_cols:
            cur.execute("ALTER TABLE study_areas ADD COLUMN hierarchy_path TEXT")

        # 2. Infrastructure columns
        cur.execute("PRAGMA table_info(infrastructure)")
        inf_cols = [c[1] for c in cur.fetchall()]
        if "locality_name" not in inf_cols:
            cur.execute("ALTER TABLE infrastructure ADD COLUMN locality_name TEXT")
        if "sub_ward" not in inf_cols:
            cur.execute("ALTER TABLE infrastructure ADD COLUMN sub_ward TEXT")

        # 3. Road segments columns
        cur.execute("PRAGMA table_info(road_segments)")
        rd_cols = [c[1] for c in cur.fetchall()]
        if "locality_name" not in rd_cols:
            cur.execute("ALTER TABLE road_segments ADD COLUMN locality_name TEXT")
        if "elevation_m" not in rd_cols:
            cur.execute("ALTER TABLE road_segments ADD COLUMN elevation_m REAL")

        # 4. Buildings table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS buildings (
                building_id TEXT PRIMARY KEY,
                name TEXT,
                building_type TEXT NOT NULL DEFAULT 'residential',
                study_area_id TEXT REFERENCES study_areas(study_area_id) ON DELETE SET NULL,
                locality_name TEXT,
                geometry JSON NOT NULL,
                centroid JSON,
                height_m REAL,
                levels INTEGER,
                ground_elevation_m REAL,
                vulnerability_index REAL DEFAULT 0.0,
                properties JSON,
                source TEXT DEFAULT 'OpenStreetMap',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 5. Locality alerts table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS locality_alerts (
                alert_id TEXT PRIMARY KEY,
                locality_name TEXT NOT NULL,
                study_area_id TEXT REFERENCES study_areas(study_area_id) ON DELETE SET NULL,
                severity_level TEXT NOT NULL,
                headline TEXT NOT NULL,
                description TEXT NOT NULL,
                expected_water_depth_m REAL,
                onset_timestamp TEXT,
                expiry_timestamp TEXT,
                recommended_action TEXT,
                source TEXT DEFAULT 'EIDT Flood Early Warning Engine',
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 6. Data provenance logs table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS data_provenance_logs (
                log_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                connector_name TEXT NOT NULL,
                retrieval_timestamp TEXT NOT NULL,
                status TEXT NOT NULL,
                records_ingested INTEGER DEFAULT 0,
                spatial_extent JSON,
                checksum TEXT,
                details TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, description) VALUES (?, ?)",
            (version, "Regional administrative hierarchy, locality columns, buildings, locality_alerts, data_provenance_logs")
        )

    elif version == "002_flood_hazard_module":
        cur.execute("""
            CREATE TABLE IF NOT EXISTS weather_forecasts (
                forecast_id TEXT PRIMARY KEY,
                study_area_id TEXT REFERENCES study_areas(study_area_id) ON DELETE CASCADE,
                locality_id TEXT,
                issue_time TEXT NOT NULL,
                valid_time TEXT NOT NULL,
                retrieval_time TEXT NOT NULL,
                latitude REAL,
                longitude REAL,
                precipitation_mm REAL NOT NULL DEFAULT 0.0,
                rain_mm REAL,
                weather_code INTEGER,
                precipitation_probability_pct REAL,
                source TEXT NOT NULL DEFAULT 'Open-Meteo',
                model_name TEXT DEFAULT 'best_match',
                units JSON,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS flood_hazard_assessments (
                assessment_id TEXT PRIMARY KEY,
                study_area_id TEXT REFERENCES study_areas(study_area_id) ON DELETE CASCADE,
                locality_name TEXT NOT NULL,
                assessment_time TEXT NOT NULL,
                valid_start_time TEXT NOT NULL,
                valid_end_time TEXT NOT NULL,
                horizon_hours INTEGER DEFAULT 24,
                forecast_rainfall_24h_mm REAL NOT NULL DEFAULT 0.0,
                forecast_rainfall_peak_1h_mm REAL DEFAULT 0.0,
                antecedent_rainfall_24h_mm REAL DEFAULT 0.0,
                elevation_mean_m REAL,
                risk_level TEXT NOT NULL DEFAULT 'LOW',
                risk_score REAL DEFAULT 0.0,
                contributing_factors JSON,
                missing_inputs JSON,
                input_coverage JSON,
                confidence_status TEXT NOT NULL DEFAULT 'MODERATE',
                model_version TEXT NOT NULL DEFAULT 'EIDT-Hazard-v1.0',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, description) VALUES (?, ?)",
            (version, "Traceable hourly forecasts and locality flood-hazard assessments")
        )

    elif version == "003_inundation_simulation_pipeline":
        cur.execute("""
            CREATE TABLE IF NOT EXISTS inundation_simulations (
                simulation_id TEXT PRIMARY KEY,
                study_area_id TEXT REFERENCES study_areas(study_area_id) ON DELETE CASCADE,
                run_name TEXT NOT NULL,
                model_type TEXT NOT NULL,
                model_version TEXT NOT NULL DEFAULT 'EIDT-Inundation-v1.0',
                product_classification TEXT NOT NULL,
                spatial_resolution_m REAL DEFAULT 30.0,
                rainfall_scenario_mm REAL NOT NULL,
                duration_hours REAL DEFAULT 24.0,
                tide_level_m REAL DEFAULT 4.2,
                soil_saturation_pct REAL DEFAULT 75.0,
                status TEXT NOT NULL DEFAULT 'COMPLETED',
                execution_duration_sec REAL DEFAULT 0.0,
                peak_depth_m REAL DEFAULT 0.0,
                mean_depth_m REAL DEFAULT 0.0,
                inundated_area_sq_km REAL DEFAULT 0.0,
                exposed_buildings_count INTEGER DEFAULT 0,
                exposed_roads_count INTEGER DEFAULT 0,
                exposed_facilities_count INTEGER DEFAULT 0,
                exposed_population_est INTEGER DEFAULT 0,
                depth_distribution JSON,
                extent_geojson JSON,
                water_arrival_time_min INTEGER,
                input_provenance JSON,
                uncertainty_metadata JSON,
                limitation_notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, description) VALUES (?, ?)",
            (version, "Physically defensible flood inundation, water depth, and impact simulation pipeline")
        )

    elif version == "004_multi_hazard_platform":
        cur.execute("""
            CREATE TABLE IF NOT EXISTS multi_hazard_alerts (
                alert_id TEXT PRIMARY KEY,
                hazard_type TEXT NOT NULL,
                geographic_scope TEXT NOT NULL,
                study_area_id TEXT REFERENCES study_areas(study_area_id) ON DELETE SET NULL,
                severity_level TEXT NOT NULL,
                headline TEXT NOT NULL,
                description TEXT NOT NULL,
                rationale TEXT,
                lifecycle_status TEXT NOT NULL DEFAULT 'ISSUED',
                is_official_warning INTEGER DEFAULT 0,
                issuing_authority TEXT NOT NULL,
                onset_timestamp TEXT,
                expiry_timestamp TEXT,
                recommended_action TEXT,
                evidence_data JSON,
                model_version TEXT,
                deduplication_hash TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS hazard_assessments (
                assessment_id TEXT PRIMARY KEY,
                hazard_type TEXT NOT NULL,
                study_area_id TEXT REFERENCES study_areas(study_area_id) ON DELETE CASCADE,
                locality_name TEXT NOT NULL,
                assessment_time TEXT NOT NULL,
                valid_start_time TEXT NOT NULL,
                valid_end_time TEXT NOT NULL,
                horizon_hours INTEGER DEFAULT 24,
                risk_category TEXT NOT NULL DEFAULT 'LOW',
                risk_score REAL DEFAULT 0.0,
                metrics JSON,
                contributing_factors JSON,
                missing_inputs JSON,
                confidence_status TEXT NOT NULL,
                model_version TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, description) VALUES (?, ?)",
            (version, "Multi-hazard alert lifecycle and cross-hazard locality risk assessment platform")
        )

    elif version == "005_emergency_routing_platform":
        cur.execute("""
            CREATE TABLE IF NOT EXISTS emergency_facilities (
                facility_id TEXT PRIMARY KEY,
                source_id TEXT,
                source_name TEXT NOT NULL DEFAULT 'OpenStreetMap / MCGM Civic Directory',
                name TEXT NOT NULL,
                facility_type TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                locality_name TEXT,
                ward_id TEXT REFERENCES study_areas(study_area_id) ON DELETE SET NULL,
                verification_status TEXT NOT NULL DEFAULT 'VERIFIED_MUNICIPAL',
                last_verified_at TEXT DEFAULT CURRENT_TIMESTAMP,
                operating_status TEXT NOT NULL DEFAULT 'OPERATIONAL',
                contact_phone TEXT,
                capacity_total INTEGER,
                capacity_available INTEGER,
                capacity_status_notes TEXT,
                is_officially_designated_shelter INTEGER DEFAULT 0,
                accessibility_notes TEXT,
                provenance_url TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS road_restrictions (
                restriction_id TEXT PRIMARY KEY,
                road_segment_id TEXT REFERENCES road_segments(road_segment_id) ON DELETE CASCADE,
                road_name TEXT,
                restriction_type TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'BLOCKED',
                is_hypothetical_scenario INTEGER DEFAULT 0,
                scenario_id TEXT,
                cause_description TEXT NOT NULL,
                issuing_authority TEXT NOT NULL,
                valid_from TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                valid_until TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS route_requests (
                request_id TEXT PRIMARY KEY,
                origin_lat REAL NOT NULL,
                origin_lon REAL NOT NULL,
                destination_lat REAL NOT NULL,
                destination_lon REAL NOT NULL,
                target_facility_id TEXT REFERENCES emergency_facilities(facility_id) ON DELETE SET NULL,
                routing_mode TEXT NOT NULL,
                include_alternatives INTEGER DEFAULT 1,
                distance_m REAL,
                estimated_duration_sec REAL,
                hazard_exposure_summary JSON,
                route_geometry JSON,
                unassessed_segments_count INTEGER DEFAULT 0,
                data_timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                safety_disclaimer TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS evacuation_scenarios (
                scenario_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                target_ward_id TEXT REFERENCES study_areas(study_area_id) ON DELETE SET NULL,
                active_restrictions JSON,
                flood_depth_threshold_cm REAL DEFAULT 30.0,
                created_by TEXT DEFAULT 'EIDT Emergency Planner',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, description) VALUES (?, ?)",
            (version, "Emergency facilities, shelters, road restrictions, and evacuation routing platform")
        )

    elif version == "006_monitoring_and_alert_orchestration":
        cur.execute("""
            CREATE TABLE IF NOT EXISTS source_health_records (
                source_id TEXT PRIMARY KEY,
                source_name TEXT NOT NULL,
                category TEXT NOT NULL,
                health_status TEXT NOT NULL DEFAULT 'healthy',
                freshness_threshold_minutes INTEGER NOT NULL DEFAULT 180,
                expected_cadence_minutes INTEGER NOT NULL DEFAULT 60,
                last_successful_retrieval TEXT,
                last_attempt_at TEXT,
                consecutive_failures INTEGER DEFAULT 0,
                error_details TEXT,
                records_count INTEGER DEFAULT 0,
                metrics JSON,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_ingestion_jobs (
                job_id TEXT PRIMARY KEY,
                job_name TEXT NOT NULL,
                source_id TEXT NOT NULL,
                schedule_interval TEXT NOT NULL,
                scheduled_at TEXT DEFAULT CURRENT_TIMESTAMP,
                started_at TEXT,
                completed_at TEXT,
                status TEXT NOT NULL,
                records_retrieved INTEGER DEFAULT 0,
                records_accepted INTEGER DEFAULT 0,
                records_rejected INTEGER DEFAULT 0,
                records_deduplicated INTEGER DEFAULT 0,
                retry_count INTEGER DEFAULT 0,
                error_category TEXT,
                execution_log TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sched_jobs_name ON scheduled_ingestion_jobs(job_name);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sched_jobs_source ON scheduled_ingestion_jobs(source_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sched_jobs_status ON scheduled_ingestion_jobs(status);")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS ingested_observations (
                observation_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                source_record_id TEXT,
                variable_name TEXT NOT NULL,
                value REAL NOT NULL,
                unit TEXT NOT NULL,
                locality_name TEXT,
                latitude REAL,
                longitude REAL,
                spatial_ref JSON,
                observed_at TEXT,
                issued_at TEXT,
                valid_at TEXT,
                retrieved_at TEXT NOT NULL,
                processed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                product_version TEXT,
                quality_flags JSON,
                ingestion_run_id TEXT,
                provenance_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ingested_obs_src ON ingested_observations(source_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ingested_obs_var ON ingested_observations(variable_name);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ingested_obs_loc ON ingested_observations(locality_name);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ingested_obs_valid_at ON ingested_observations(valid_at);")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS alert_lifecycle_events (
                event_id TEXT PRIMARY KEY,
                alert_id TEXT NOT NULL,
                previous_state TEXT,
                new_state TEXT NOT NULL,
                transition_reason TEXT NOT NULL,
                triggered_by TEXT DEFAULT 'SYSTEM',
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_alert_events_alert ON alert_lifecycle_events(alert_id);")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS alert_notifications (
                notification_id TEXT PRIMARY KEY,
                alert_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                recipient_target TEXT NOT NULL,
                status TEXT NOT NULL,
                attempt_count INTEGER DEFAULT 1,
                payload_summary TEXT,
                provider_response JSON,
                error_message TEXT,
                sent_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_alert_notif_alert ON alert_notifications(alert_id);")

        cur.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, description) VALUES (?, ?)",
            (version, "Real-time monitoring, ingestion jobs, observations, alert lifecycle, and notification records")
        )

    elif version == "007_historical_validation_and_replay":
        cur.execute("""
            CREATE TABLE IF NOT EXISTS historical_hazard_events (
                event_id TEXT PRIMARY KEY,
                event_name TEXT NOT NULL,
                hazard_type TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                geographic_scope TEXT NOT NULL,
                affected_localities JSON NOT NULL,
                primary_source TEXT NOT NULL,
                source_url TEXT,
                license TEXT,
                evidence_classification TEXT NOT NULL,
                confidence_flag TEXT NOT NULL DEFAULT 'HIGH',
                meteorological_metrics JSON,
                impact_summary TEXT,
                retrieved_at TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_hist_events_type ON historical_hazard_events(hazard_type);")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS evaluation_datasets (
                dataset_id TEXT PRIMARY KEY,
                dataset_name TEXT NOT NULL,
                hazard_type TEXT NOT NULL,
                version TEXT NOT NULL,
                split_strategy TEXT NOT NULL,
                train_start TEXT,
                train_end TEXT,
                test_start TEXT,
                test_end TEXT,
                total_samples INTEGER DEFAULT 0,
                train_samples_count INTEGER DEFAULT 0,
                test_samples_count INTEGER DEFAULT 0,
                leakage_controls JSON NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS evaluation_dataset_samples (
                sample_id TEXT PRIMARY KEY,
                dataset_id TEXT REFERENCES evaluation_datasets(dataset_id) ON DELETE CASCADE,
                event_id TEXT REFERENCES historical_hazard_events(event_id) ON DELETE CASCADE,
                locality_id TEXT NOT NULL,
                locality_name TEXT NOT NULL,
                prediction_issue_time TEXT NOT NULL,
                valid_time TEXT NOT NULL,
                predictors JSON NOT NULL,
                reference_outcome REAL NOT NULL,
                reference_source TEXT NOT NULL,
                reference_time TEXT NOT NULL,
                split_assignment TEXT NOT NULL,
                quality_flags JSON
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_eval_samples_ds ON evaluation_dataset_samples(dataset_id);")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS evaluation_runs (
                run_id TEXT PRIMARY KEY,
                model_id TEXT NOT NULL,
                model_version TEXT NOT NULL,
                dataset_id TEXT REFERENCES evaluation_datasets(dataset_id) ON DELETE CASCADE,
                hazard_type TEXT NOT NULL,
                evaluation_type TEXT NOT NULL,
                executed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                sample_size INTEGER NOT NULL,
                status TEXT NOT NULL,
                limitation_notes TEXT
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS evaluation_metrics (
                metric_id TEXT PRIMARY KEY,
                run_id TEXT REFERENCES evaluation_runs(run_id) ON DELETE CASCADE,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                baseline_value REAL,
                sample_size INTEGER NOT NULL,
                confidence_interval_low REAL,
                confidence_interval_high REAL,
                metric_definition TEXT NOT NULL
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_eval_metrics_run ON evaluation_metrics(run_id);")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS historical_replay_runs (
                replay_id TEXT PRIMARY KEY,
                event_id TEXT REFERENCES historical_hazard_events(event_id) ON DELETE CASCADE,
                replay_name TEXT NOT NULL,
                hazard_type TEXT NOT NULL,
                replay_mode TEXT NOT NULL,
                issue_timestamp TEXT NOT NULL,
                model_version TEXT NOT NULL,
                input_snapshots JSON NOT NULL,
                predicted_outcomes JSON NOT NULL,
                observed_benchmark JSON NOT NULL,
                concordance_metrics JSON NOT NULL,
                status TEXT NOT NULL,
                is_isolated_from_live BOOLEAN DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_replay_runs_event ON historical_replay_runs(event_id);")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS model_calibration_runs (
                calibration_id TEXT PRIMARY KEY,
                model_id TEXT NOT NULL,
                model_version TEXT NOT NULL,
                method TEXT NOT NULL,
                dataset_id TEXT REFERENCES evaluation_datasets(dataset_id),
                brier_score_before REAL NOT NULL,
                brier_score_after REAL NOT NULL,
                reliability_bins JSON NOT NULL,
                calibrator_artifact_path TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, description) VALUES (?, ?)",
            (version, "Historical disaster event catalogue, evaluation datasets, probability calibration, and replay engine")
        )

    elif version == "008_maharashtra_wide_scaling":
        # 1. Study areas columns
        cur.execute("PRAGMA table_info(study_areas)")
        sa_cols = [c[1] for c in cur.fetchall()]
        if "aliases" not in sa_cols:
            cur.execute("ALTER TABLE study_areas ADD COLUMN aliases JSON DEFAULT '[]'")
        if "division_id" not in sa_cols:
            cur.execute("ALTER TABLE study_areas ADD COLUMN division_id TEXT")
        if "district_id" not in sa_cols:
            cur.execute("ALTER TABLE study_areas ADD COLUMN district_id TEXT")
        if "crs" not in sa_cols:
            cur.execute("ALTER TABLE study_areas ADD COLUMN crs TEXT DEFAULT 'EPSG:4326'")
        if "boundary_version" not in sa_cols:
            cur.execute("ALTER TABLE study_areas ADD COLUMN boundary_version TEXT DEFAULT 'SurveyOfIndia-Census2011/MRSAC-v2.1'")
        if "effective_date" not in sa_cols:
            cur.execute("ALTER TABLE study_areas ADD COLUMN effective_date TEXT")
        if "is_verified" not in sa_cols:
            cur.execute("ALTER TABLE study_areas ADD COLUMN is_verified INTEGER DEFAULT 1")
        if "simplified_geometry" not in sa_cols:
            cur.execute("ALTER TABLE study_areas ADD COLUMN simplified_geometry JSON")

        # 2. Regional Ingestion Spatial Tiles Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS regional_ingestion_tiles (
                tile_id TEXT PRIMARY KEY,
                district_id TEXT NOT NULL,
                min_lat REAL NOT NULL,
                min_lon REAL NOT NULL,
                max_lat REAL NOT NULL,
                max_lon REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'IDLE',
                retry_count INTEGER NOT NULL DEFAULT 0,
                last_ingested_at TEXT,
                data_hash TEXT,
                records_count INTEGER NOT NULL DEFAULT 0,
                error_message TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 3. API Metric Logs Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS api_metric_logs (
                log_id TEXT PRIMARY KEY,
                correlation_id TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                method TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                duration_ms REAL NOT NULL,
                user_agent TEXT,
                client_ip TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 4. Composite Indexes
        cur.execute("CREATE INDEX IF NOT EXISTS idx_study_areas_type_parent ON study_areas (region_type, parent_region_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_study_areas_hierarchy ON study_areas (hierarchy_path);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_study_areas_district ON study_areas (district_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_study_areas_division ON study_areas (division_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_weather_obs_time_area ON weather_observations (timestamp, study_area_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_infra_ward_fac ON infrastructure (ward_id, feature_type);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_road_loc_class ON road_segments (locality_name, road_class);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_hazard_alerts_active_scope ON multi_hazard_alerts (lifecycle_status, geographic_scope, severity_level);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_regional_tiles_dist_status ON regional_ingestion_tiles (district_id, status);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_api_metrics_time_endpoint ON api_metric_logs (timestamp, endpoint);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_api_metrics_correlation ON api_metric_logs (correlation_id);")

        cur.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, description) VALUES (?, ?)",
            (version, "Maharashtra statewide administrative hierarchy, regional tiled ingestion, performance indexes, and observability logs")
        )

    conn.commit()
    cur.close()

def run_migrations(check_only: bool = False) -> int:
    conn, dialect = get_connection()
    logger.info(f"Connected to database engine: {dialect}")
    
    ensure_migration_table(conn, dialect)
    applied = get_applied_migrations(conn)

    migration_files = sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql")))
    
    if check_only:
        print(f"\n--- Migration Status ({dialect}) ---")
        for f in migration_files:
            v = os.path.splitext(os.path.basename(f))[0]
            status = "APPLIED" if v in applied else "PENDING"
            print(f"  [{status}] {v}")
        conn.close()
        return 0

    pending_count = 0
    for f in migration_files:
        version = os.path.splitext(os.path.basename(f))[0]
        if version in applied:
            logger.info(f"Migration '{version}' already applied. Skipping.")
            continue

        logger.info(f"Applying migration '{version}' on {dialect}...")
        try:
            if dialect == "postgresql":
                with open(f, "r", encoding="utf-8") as sql_file:
                    sql_content = sql_file.read()
                cur = conn.cursor()
                cur.execute(sql_content)
                conn.commit()
                cur.close()
            else:
                run_sqlite_migration(conn, version)

            logger.info(f"Successfully applied migration '{version}'.")
            pending_count += 1
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to apply migration '{version}': {e}")
            conn.close()
            raise

    # Also apply to SQLite if PostgreSQL was primary and SQLite exists (keep local portable fallback in sync)
    if dialect == "postgresql":
        sqlite_path = os.path.join(backend_dir, "eidt_mumbai.db")
        if os.path.exists(sqlite_path):
            try:
                import sqlite3
                sq_conn = sqlite3.connect(sqlite_path)
                ensure_migration_table(sq_conn, "sqlite")
                for f in migration_files:
                    v = os.path.splitext(os.path.basename(f))[0]
                    run_sqlite_migration(sq_conn, v)
                sq_conn.close()
                logger.info("Synchronized migration with SQLite fallback database.")
            except Exception as e:
                logger.warning(f"Could not synchronize SQLite fallback database: {e}")

    conn.close()
    logger.info(f"Migration run complete. Applied {pending_count} new migration(s).")
    return pending_count

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EIDT Database Migration Runner")
    parser.add_argument("--status", action="store_true", help="Display migration status without executing")
    args = parser.parse_args()
    run_migrations(check_only=args.status)
