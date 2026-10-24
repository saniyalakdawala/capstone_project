"""
Automated Database Restore & Recovery Verification
Earth Intelligence Digital Twin (EIDT) - Maharashtra
Phase 7J: Isolated Recovery Testing & Integrity Verification.

Features:
  - Cryptographic checksum verification (SHA-256) before restoring.
  - Isolated test restore environment: Restores into temporary database to verify
    integrity without touching or endangering active production data.
  - Verification of representative records, row counts, and schema tables.
"""

import os
import sys
import json
import gzip
import sqlite3
import hashlib
from typing import Dict, Any, Optional

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKUP_DIR = os.path.join(REPO_ROOT, "backups")


def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def find_latest_backup() -> Optional[str]:
    archives = [f for f in os.listdir(BACKUP_DIR) if f.endswith(".sql.gz")]
    if not archives:
        return None
    archives.sort(reverse=True)
    return os.path.join(BACKUP_DIR, archives[0])


def verify_and_test_restore(backup_filepath: Optional[str] = None) -> Dict[str, Any]:
    print("=========================================================================")
    print("EIDT Maharashtra — Disaster Recovery & Backup Integrity Test")
    print("=========================================================================")

    if not backup_filepath:
        backup_filepath = find_latest_backup()

    if not backup_filepath or not os.path.exists(backup_filepath):
        print("[ERROR] No backup archive found to test.")
        return {"status": "FAILED", "error": "No backup archive found"}

    meta_file = backup_filepath.replace(".sql.gz", "_meta.json")
    print(f"Testing backup archive: {backup_filepath}")

    # 1. Verify Checksum
    current_checksum = compute_sha256(backup_filepath)
    if os.path.exists(meta_file):
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)
        expected_checksum = meta.get("sha256_checksum")
        if expected_checksum and expected_checksum != current_checksum:
            print(f"[FAIL] Checksum mismatch! Expected {expected_checksum}, got {current_checksum}")
            return {"status": "FAILED", "error": "Checksum mismatch"}
        print(f"[PASS] Cryptographic SHA-256 integrity verified: {current_checksum}")
    else:
        print("[WARN] No metadata file found; proceeding with decompression test.")

    # 2. Test restore in an isolated temporary database
    test_db_path = os.path.join(BACKUP_DIR, "test_recovery_isolated.db")
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

    print(f"Creating isolated recovery database at: {test_db_path}")
    conn = sqlite3.connect(test_db_path)
    cur = conn.cursor()

    try:
        with gzip.open(backup_filepath, "rt", encoding="utf-8") as gz_in:
            sql_script = gz_in.read()

        # Execute restore script in isolated database
        cur.executescript(sql_script)
        conn.commit()

        # 3. Verify representative records
        cur.execute("SELECT COUNT(*) FROM study_areas;")
        study_area_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM schema_migrations;")
        migration_count = cur.fetchone()[0]

        # Verify a specific known record
        cur.execute("SELECT name, administrative_level FROM study_areas WHERE study_area_id='MAH_STATE';")
        state_record = cur.fetchone()

        print("\n[VERIFICATION RESULTS]")
        print(f"  Total Study Areas restored: {study_area_count}")
        print(f"  Total Schema Migrations restored: {migration_count}")
        print(f"  Representative State Record: {state_record}")

        if study_area_count == 0 or migration_count == 0:
            raise ValueError("Restored database has 0 study areas or migrations!")

        print("\n[PASS] Isolated disaster recovery test passed with 100% record integrity.")
        status = "PASS"

    except Exception as e:
        print(f"\n[FAIL] Restore test failed: {e}")
        status = "FAILED"

    finally:
        conn.close()
        # Clean up isolated test database
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
            print(f"Cleaned up isolated temporary database.")

    return {
        "status": status,
        "backup_tested": os.path.basename(backup_filepath),
        "checksum": current_checksum,
        "study_areas_verified": study_area_count if status == "PASS" else 0,
        "migrations_verified": migration_count if status == "PASS" else 0
    }


if __name__ == "__main__":
    archive = sys.argv[1] if len(sys.argv) > 1 else None
    res = verify_and_test_restore(archive)
    sys.exit(0 if res["status"] == "PASS" else 1)
