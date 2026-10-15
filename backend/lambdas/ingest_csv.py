"""
AWS Lambda Handler: Streaming S3 CSV Ingester.
Triggered asynchronously by S3 's3:ObjectCreated:*' events.
Streams CSV line-by-line, performs defensive sanitization, executes high-speed bulk COPY
into PostgreSQL, logs quarantined records, and triggers n8n Workflow B via webhook.
"""

import os
import io
import csv
import json
import re
import uuid
from typing import Dict, Any, List, Tuple, Optional
import boto3
import urllib.request
import urllib.error
import psycopg
from psycopg.rows import dict_row

# Configuration from Environment
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "loan_engine")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DATABASE_URL = os.getenv("DATABASE_URL")
N8N_WORKFLOW_B_WEBHOOK_URL = os.getenv(
    "N8N_WORKFLOW_B_WEBHOOK_URL", 
    "http://localhost:5678/webhook/match-users"
)
BATCH_SIZE = int(os.getenv("INGESTION_BATCH_SIZE", "2000"))

s3_client = boto3.client("s3")


def get_db_connection() -> psycopg.Connection:
    """Connect to PostgreSQL with autocommit=False for atomic transactions."""
    if DATABASE_URL:
        return psycopg.connect(DATABASE_URL, row_factory=dict_row)
    return psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        row_factory=dict_row
    )


def sanitize_number(val: Any) -> Optional[float]:
    """Strip currency symbols, commas, and whitespace, then convert to float."""
    if val is None:
        return None
    s = str(val).strip()
    s = re.sub(r"[^\d.-]", "", s)
    try:
        return float(s) if s else None
    except ValueError:
        return None


def validate_and_clean_row(row_idx: int, raw_row: Dict[str, str]) -> Tuple[Optional[Tuple], Optional[Dict]]:
    """
    Defensive Data Sanitation:
    Validates types and ranges. Returns (clean_tuple, None) on success,
    or (None, rejection_dict) on validation failure.
    """
    # Normalize headers
    normalized = {k.strip().lower().replace(" ", "_"): v.strip() for k, v in raw_row.items() if k}
    
    user_id = normalized.get("user_id") or normalized.get("id")
    email = normalized.get("email")
    raw_income = normalized.get("monthly_income") or normalized.get("income")
    raw_score = normalized.get("credit_score") or normalized.get("cibil_score") or normalized.get("score")
    employment = normalized.get("employment_status") or normalized.get("employment") or "employed"
    raw_age = normalized.get("age")

    reasons = []
    if not user_id:
        reasons.append("Missing user_id")
    if not email or "@" not in email:
        reasons.append(f"Invalid email address: '{email}'")

    income = sanitize_number(raw_income)
    if income is None or income < 0:
        reasons.append(f"Invalid monthly_income: '{raw_income}'")

    score = sanitize_number(raw_score)
    if score is None or not (300 <= int(score) <= 900):
        reasons.append(f"Credit score out of valid range (300-900): '{raw_score}'")

    age = sanitize_number(raw_age)
    if age is None or not (18 <= int(age) <= 100):
        reasons.append(f"Age out of eligible range (18-100): '{raw_age}'")

    clean_employment = employment.lower().replace("-", "_").replace(" ", "_")
    if clean_employment not in ["employed", "self_employed", "unemployed", "retired", "student"]:
        clean_employment = "employed"  # Default fallback

    if reasons:
        return None, {
            "row_number": row_idx,
            "raw_data": raw_row,
            "rejection_reason": "; ".join(reasons)
        }

    return (
        user_id,
        email.lower(),
        round(income, 2),
        int(score),
        clean_employment,
        int(age)
    ), None


def trigger_n8n_webhook(job_id: str, row_count: int) -> None:
    """Notify n8n Workflow B that new users are ready for matching."""
    payload = json.dumps({
        "job_id": job_id,
        "valid_rows": row_count,
        "timestamp": str(uuid.uuid4())
    }).encode("utf-8")

    req = urllib.request.Request(
        N8N_WORKFLOW_B_WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            print(f"[+] Successfully notified n8n webhook: HTTP {response.status}")
    except urllib.error.URLError as e:
        # Note: Do not fail the ingestion job if n8n is temporarily offline or in test mode
        print(f"[!] Warning: Could not reach n8n webhook at {N8N_WORKFLOW_B_WEBHOOK_URL}: {e}")


def process_csv_stream(file_stream: io.TextIOBase, job_id: str, s3_key: str, file_name: str) -> Dict[str, Any]:
    """
    Stream rows from text stream, perform validation, and bulk insert into PostgreSQL.
    Leverages PostgreSQL's native COPY command for maximum throughput.
    """
    reader = csv.DictReader(file_stream)
    if not reader.fieldnames:
        raise ValueError("Uploaded file is empty or missing CSV headers.")

    conn = get_db_connection()
    total_rows = 0
    valid_tuples: List[Tuple] = []
    quarantined_records: List[Dict] = []

    try:
        with conn.cursor() as cur:
            # 1. Create Ingestion Job Record
            cur.execute(
                """
                INSERT INTO ingestion_jobs (id, s3_key, file_name, status)
                VALUES (%s, %s, %s, 'PROCESSING')
                ON CONFLICT (id) DO UPDATE SET status = 'PROCESSING';
                """,
                (job_id, s3_key, file_name)
            )
            conn.commit()

            # 2. Process CSV line-by-line (streaming)
            for idx, raw_row in enumerate(reader, start=1):
                total_rows += 1
                clean_tuple, bad_record = validate_and_clean_row(idx, raw_row)
                
                if clean_tuple:
                    # Prepend job_id
                    valid_tuples.append((job_id, *clean_tuple))
                else:
                    quarantined_records.append(bad_record)

                # Batch flush to avoid unbounded memory growth
                if len(valid_tuples) >= BATCH_SIZE:
                    _flush_valid_rows(cur, valid_tuples)
                    valid_tuples = []

            # Flush remaining valid tuples
            if valid_tuples:
                _flush_valid_rows(cur, valid_tuples)

            # 3. Insert Quarantined Records
            if quarantined_records:
                for q in quarantined_records:
                    cur.execute(
                        """
                        INSERT INTO quarantined_records (job_id, row_number, raw_data, rejection_reason)
                        VALUES (%s, %s, %s, %s);
                        """,
                        (job_id, q["row_number"], json.dumps(q["raw_data"]), q["rejection_reason"])
                    )

            # 4. Finalize Job Status
            valid_count = total_rows - len(quarantined_records)
            cur.execute(
                """
                UPDATE ingestion_jobs
                SET status = 'COMPLETED',
                    total_rows = %s,
                    valid_rows = %s,
                    quarantined_rows = %s,
                    completed_at = NOW()
                WHERE id = %s;
                """,
                (total_rows, valid_count, len(quarantined_records), job_id)
            )
            conn.commit()

        # 5. Fire event to n8n Workflow B
        trigger_n8n_webhook(job_id, valid_count)

        return {
            "job_id": job_id,
            "status": "COMPLETED",
            "total_rows": total_rows,
            "valid_rows": valid_count,
            "quarantined_rows": len(quarantined_records)
        }

    except Exception as e:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ingestion_jobs
                SET status = 'FAILED',
                    error_message = %s,
                    completed_at = NOW()
                WHERE id = %s;
                """,
                (str(e), job_id)
            )
            conn.commit()
        raise
    finally:
        conn.close()


def _flush_valid_rows(cur: psycopg.Cursor, records: List[Tuple]) -> None:
    """Execute high-speed binary COPY into PostgreSQL users table."""
    with cur.copy(
        "COPY users (job_id, user_id, email, monthly_income, credit_score, employment_status, age) FROM STDIN"
    ) as copy:
        for r in records:
            copy.write_row(r)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda entrypoint for S3 ObjectCreated event."""
    try:
        # Check if direct invocation or S3 event
        records = event.get("Records", [])
        if not records:
            # Check for direct payload
            bucket = event.get("bucket")
            key = event.get("key")
            job_id = event.get("job_id", str(uuid.uuid4()))
        else:
            s3_info = records[0].get("s3", {})
            bucket = s3_info.get("bucket", {}).get("name")
            key = s3_info.get("object", {}).get("key")
            # Extract job_id from path uploads/{job_id}/filename.csv
            parts = key.split("/")
            job_id = parts[1] if len(parts) >= 3 else str(uuid.uuid4())

        if not bucket or not key:
            raise ValueError("Event is missing S3 bucket or key.")

        file_name = os.path.basename(key)
        print(f"[*] Ingesting file s3://{bucket}/{key} for job_id: {job_id}...")

        # Fetch S3 object stream
        response = s3_client.get_object(Bucket=bucket, Key=key)
        text_stream = io.TextIOWrapper(response["Body"], encoding="utf-8")

        result = process_csv_stream(text_stream, job_id, key, file_name)
        print(f"[+] Ingestion complete for job {job_id}: {result}")

        return {
            "statusCode": 200,
            "body": json.dumps(result)
        }

    except Exception as e:
        print(f"[-] Ingestion failed: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
