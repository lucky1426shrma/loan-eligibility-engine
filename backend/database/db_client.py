"""
Database client module for The Loan Eligibility Engine.
Supports high-throughput streaming bulk inserts via psycopg3 COPY,
schema initialization, and connection management.
"""

import os
from pathlib import Path
from contextlib import contextmanager
from typing import Generator, Any, Dict, List
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "loan_engine")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DATABASE_URL = os.getenv("DATABASE_URL")


def get_conn_str() -> str:
    """Return database connection string from environment or parameters."""
    if DATABASE_URL:
        return DATABASE_URL
    return f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


@contextmanager
def get_db_connection() -> Generator[psycopg.Connection, None, None]:
    """Context manager providing an active PostgreSQL connection."""
    conn = psycopg.connect(get_conn_str(), row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Initialize database tables and seed products from SQL files."""
    db_dir = Path(__file__).parent
    schema_file = db_dir / "schema.sql"
    seed_file = db_dir / "seed_products.sql"

    print(f"[*] Connecting to database at {DB_HOST}:{DB_PORT}/{DB_NAME}...")
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if schema_file.exists():
                print("[*] Applying schema DDL...")
                cur.execute(schema_file.read_text(encoding="utf-8"))
            if seed_file.exists():
                print("[*] Seeding default loan products...")
                cur.execute(seed_file.read_text(encoding="utf-8"))
    print("[+] Database initialized successfully.")


if __name__ == "__main__":
    init_db()
