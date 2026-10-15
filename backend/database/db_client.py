"""
Database Client Module for The Loan Eligibility Engine.
Unified database layer supporting PostgreSQL 16 (for Docker Compose and AWS RDS)
with seamless fallback to SQLite (for zero-setup standalone local runs).
"""

import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Generator, Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "loan_engine")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DATABASE_URL = os.getenv("DATABASE_URL")
LOCAL_DB_FILE = Path(__file__).parent.parent.parent / "loan_engine.db"

_PG_AVAILABLE = None


def is_postgres_available() -> bool:
    """Check if PostgreSQL instance is actively reachable."""
    global _PG_AVAILABLE
    if _PG_AVAILABLE is not None:
        return _PG_AVAILABLE

    try:
        import psycopg
        conn_str = DATABASE_URL or f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        conn = psycopg.connect(conn_str, connect_timeout=1)
        conn.close()
        _PG_AVAILABLE = True
        print("[+] Active PostgreSQL instance detected. Using PostgreSQL engine.")
        return True
    except Exception:
        _PG_AVAILABLE = False
        print(f"[!] PostgreSQL not reachable on {DB_HOST}:{DB_PORT}. Falling back to local SQLite engine ({LOCAL_DB_FILE.name}).")
        return False


def get_sqlite_conn() -> sqlite3.Connection:
    """Return a configured SQLite connection with dictionary row access."""
    conn = sqlite3.connect(LOCAL_DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def get_db_connection() -> Generator[Any, None, None]:
    """Yield an active connection (PostgreSQL or SQLite fallback)."""
    if is_postgres_available():
        import psycopg
        from psycopg.rows import dict_row
        conn_str = DATABASE_URL or f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        conn = psycopg.connect(conn_str, row_factory=dict_row)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        conn = get_sqlite_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def init_db() -> None:
    """Initialize database tables and seed loan products."""
    if is_postgres_available():
        import psycopg
        from psycopg.rows import dict_row
        db_dir = Path(__file__).parent
        schema_file = db_dir / "schema.sql"
        seed_file = db_dir / "seed_products.sql"
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                if schema_file.exists():
                    cur.execute(schema_file.read_text(encoding="utf-8"))
                if seed_file.exists():
                    cur.execute(seed_file.read_text(encoding="utf-8"))
        print("[+] PostgreSQL schema and seed data applied.")
    else:
        # SQLite schema initialization
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.executescript("""
            CREATE TABLE IF NOT EXISTS ingestion_jobs (
                id TEXT PRIMARY KEY,
                s3_key TEXT NOT NULL,
                file_name TEXT NOT NULL,
                total_rows INTEGER DEFAULT 0,
                valid_rows INTEGER DEFAULT 0,
                quarantined_rows INTEGER DEFAULT 0,
                status TEXT DEFAULT 'PENDING',
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS quarantined_records (
                id TEXT PRIMARY KEY,
                job_id TEXT,
                row_number INTEGER,
                raw_data TEXT,
                rejection_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                job_id TEXT,
                user_id TEXT NOT NULL,
                email TEXT NOT NULL,
                monthly_income REAL NOT NULL,
                credit_score INTEGER NOT NULL,
                employment_status TEXT NOT NULL,
                age INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_users_matching ON users (credit_score, monthly_income, age, employment_status);
            CREATE INDEX IF NOT EXISTS idx_users_job ON users (job_id);

            CREATE TABLE IF NOT EXISTS loan_products (
                id TEXT PRIMARY KEY,
                provider_name TEXT NOT NULL,
                product_name TEXT NOT NULL,
                interest_rate REAL NOT NULL,
                min_credit_score INTEGER NOT NULL DEFAULT 600,
                min_monthly_income REAL NOT NULL DEFAULT 0,
                min_age INTEGER NOT NULL DEFAULT 21,
                max_age INTEGER NOT NULL DEFAULT 65,
                allowed_employment_statuses TEXT DEFAULT 'employed,self_employed',
                processing_fee_pct REAL DEFAULT 1.0,
                max_loan_amount REAL DEFAULT 2500000,
                source_url TEXT,
                is_active INTEGER DEFAULT 1,
                last_crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (provider_name, product_name)
            );

            CREATE TABLE IF NOT EXISTS archetype_rationales_cache (
                archetype_key TEXT PRIMARY KEY,
                credit_tier TEXT NOT NULL,
                employment_type TEXT NOT NULL,
                income_bracket TEXT NOT NULL,
                matched_products TEXT NOT NULL,
                rationale_template TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS matches (
                id TEXT PRIMARY KEY,
                job_id TEXT,
                user_id TEXT,
                product_id TEXT,
                match_score REAL NOT NULL,
                archetype_key TEXT,
                eligibility_reason TEXT,
                is_notified INTEGER DEFAULT 0,
                notified_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (user_id, product_id, job_id)
            );
            """)

            # Seed products into SQLite if empty
            cur.execute("SELECT COUNT(*) AS cnt FROM loan_products;")
            if cur.fetchone()[0] == 0:
                cur.executescript("""
                INSERT OR IGNORE INTO loan_products (
                    id, provider_name, product_name, interest_rate, min_credit_score, 
                    min_monthly_income, min_age, max_age, allowed_employment_statuses, 
                    processing_fee_pct, max_loan_amount, source_url
                ) VALUES 
                ('P101', 'HDFC Bank', 'Personal Loan for Salaried', 10.50, 720, 50000, 21, 60, 'employed', 1.0, 4000000, 'https://www.hdfcbank.com/personal/borrow/popular-loans/personal-loan'),
                ('P102', 'ICICI Bank', 'Instant Personal Loan', 10.85, 700, 35000, 23, 58, 'employed,self_employed', 1.25, 5000000, 'https://www.icicibank.com/personal-banking/loans/personal-loan'),
                ('P103', 'State Bank of India', 'SBI Xpress Credit', 11.15, 675, 30000, 21, 60, 'employed', 0.75, 2000000, 'https://sbi.co.in/web/personal-banking/loans/personal-loans'),
                ('P104', 'Axis Bank', 'Quick Personal Loan', 10.75, 710, 40000, 21, 60, 'employed,self_employed', 1.5, 4000000, 'https://www.axisbank.com/retail/loans/personal-loan'),
                ('P105', 'Bajaj Finserv', 'Flexi Personal Loan', 12.50, 650, 25000, 21, 65, 'employed,self_employed', 2.0, 3500000, 'https://www.bajajfinserv.in/personal-loan'),
                ('P106', 'Kotak Mahindra Bank', 'Kotak Smart Personal Loan', 10.99, 730, 45000, 21, 58, 'employed', 1.0, 2500000, 'https://www.kotak.com/en/personal-banking/loans/personal-loan.html');

                INSERT OR IGNORE INTO archetype_rationales_cache (
                    archetype_key, credit_tier, employment_type, income_bracket, matched_products, rationale_template
                ) VALUES 
                ('PRIME_employed_HIGH_HDFCBank_ICICIBank', 'PRIME', 'employed', 'HIGH', 'HDFC Bank, ICICI Bank',
                 'Hi {{user_name}}, as a salaried applicant with a prime credit score, you qualify for pre-approved terms with {{matched_products}} starting at {{top_rate}}% p.a. with zero collateral.'),
                ('NEAR_PRIME_employed_MID_BajajFinserv_SBISBIXpressCredit', 'NEAR_PRIME', 'employed', 'MID', 'Bajaj Finserv, SBI',
                 'Hi {{user_name}}, your stable salaried income qualifies you for {{matched_products}} with flexible repayment and starting rate of {{top_rate}}% p.a.');
                """)
        print(f"[+] SQLite local schema and seed data applied to {LOCAL_DB_FILE.name}.")


if __name__ == "__main__":
    init_db()
