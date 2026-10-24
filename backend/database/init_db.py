"""
Database initialization script for Earth Intelligence Digital Twin (EIDT)
Supports PostgreSQL with fallback to SQLite for local portable deployment.
"""
import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

DB_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "postgres")
DB_NAME = os.getenv("POSTGRES_DB", "eidt_mumbai")

def init_postgres():
    try:
        conn = psycopg2.connect(
            dbname="postgres",
            user=DB_USER,
            password=DB_PASS,
            host=DB_HOST,
            port=DB_PORT,
            connect_timeout=3
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (DB_NAME,))
        exists = cur.fetchone()
        if not exists:
            cur.execute(f'CREATE DATABASE "{DB_NAME}";')
            print(f"[PostgreSQL] Created database '{DB_NAME}' successfully.")
        else:
            print(f"[PostgreSQL] Database '{DB_NAME}' already exists.")
        cur.close()
        conn.close()

        # For new database creation, run schema.sql; for existing databases, run safe migrations
        from database.migrate import run_migrations
        if not exists:
            schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
            if os.path.exists(schema_path):
                with open(schema_path, "r", encoding="utf-8") as f:
                    schema_sql = f.read()
                db_conn = psycopg2.connect(
                    dbname=DB_NAME,
                    user=DB_USER,
                    password=DB_PASS,
                    host=DB_HOST,
                    port=DB_PORT
                )
                db_conn.autocommit = True
                db_cur = db_conn.cursor()
                db_cur.execute(schema_sql)
                db_cur.close()
                db_conn.close()
                print(f"[PostgreSQL] Executed schema.sql on new '{DB_NAME}' database.")
        else:
            print(f"[PostgreSQL] Database '{DB_NAME}' exists; running safe migrations...")
            run_migrations()
        return True
    except Exception as e:
        print(f"[PostgreSQL] Warning/Error connecting to PostgreSQL: {e}")
        return False

if __name__ == "__main__":
    success = init_postgres()
    print("Postgres initialization result:", success)

