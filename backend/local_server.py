"""
Local Development API Server & Cloud Simulator.
Provides local endpoints matching the AWS API Gateway & S3 Presigned URL contracts,
allowing 100% end-to-end testing and video demonstration without incurring AWS costs.
"""

import os
import io
import csv
import uuid
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from dotenv import load_dotenv

from backend.database.db_client import (
    get_db_connection, 
    init_db, 
    is_postgres_available, 
    LOCAL_DB_FILE
)

load_dotenv()

app = FastAPI(title="The Loan Eligibility Engine - Local Runner")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    """Ensure database schema is applied on startup."""
    try:
        init_db()
    except Exception as e:
        print(f"[!] Database init note: {e}")


@app.get("/upload-url")
def get_presigned_url(filename: str = "users.csv"):
    """Simulates S3 Presigned URL generator locally."""
    clean_name = os.path.basename(filename)
    if not clean_name.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files supported.")

    job_id = str(uuid.uuid4())
    upload_url = f"http://localhost:8000/local-upload/{job_id}/{clean_name}"
    
    return {
        "job_id": job_id,
        "s3_key": f"uploads/{job_id}/{clean_name}",
        "upload_url": upload_url,
        "expires_in": 900,
        "mode": "local_simulator"
    }


def sanitize_number(val: Any) -> Optional[float]:
    if val is None:
        return None
    s = str(val).strip()
    s = re.sub(r"[^\d.-]", "", s)
    try:
        return float(s) if s else None
    except ValueError:
        return None


def execute_matching_funnel(job_id: str):
    """
    Executes the 3-Stage Optimization Matching Funnel locally.
    Used when n8n is not running in background or for instant local verification.
    """
    with get_db_connection() as conn:
        cur = conn.cursor()
        
        # Stage 1: Fast SQL Indexed Hard Pre-Filter
        if is_postgres_available():
            query = """
            SELECT 
              u.id AS user_db_id, u.user_id, u.email, u.monthly_income, u.credit_score, u.employment_status, u.age,
              p.id AS product_db_id, p.provider_name, p.product_name, p.interest_rate, p.min_credit_score, p.min_monthly_income
            FROM users u
            INNER JOIN loan_products p 
              ON p.is_active = TRUE
             AND u.credit_score >= p.min_credit_score
             AND u.monthly_income >= p.min_monthly_income
             AND u.age BETWEEN p.min_age AND p.max_age
             AND u.employment_status = ANY(p.allowed_employment_statuses)
            WHERE u.job_id = %s::uuid
            ORDER BY u.user_id, p.interest_rate ASC;
            """
            cur.execute(query, (job_id,))
        else:
            query = """
            SELECT 
              u.id AS user_db_id, u.user_id, u.email, u.monthly_income, u.credit_score, u.employment_status, u.age,
              p.id AS product_db_id, p.provider_name, p.product_name, p.interest_rate, p.min_credit_score, p.min_monthly_income
            FROM users u
            INNER JOIN loan_products p 
              ON p.is_active = 1
             AND u.credit_score >= p.min_credit_score
             AND u.monthly_income >= p.min_monthly_income
             AND u.age BETWEEN p.min_age AND p.max_age
            WHERE u.job_id = ?
            ORDER BY u.user_id, p.interest_rate ASC;
            """
            cur.execute(query, (job_id,))

        rows = cur.fetchall()
        if not rows:
            return

        # Stage 2: Heuristic Scoring & Ranking (Top-2 per user)
        users_map = {}
        for r in rows:
            uid = r["user_id"]
            if uid not in users_map:
                users_map[uid] = {
                    "user_db_id": r["user_db_id"],
                    "user_id": uid,
                    "email": r["email"],
                    "monthly_income": float(r["monthly_income"]),
                    "credit_score": int(r["credit_score"]),
                    "employment_status": r["employment_status"],
                    "candidates": []
                }
            
            rate_score = max(0.0, 40.0 * (1.0 - ((float(r["interest_rate"]) - 9.0) / 10.0)))
            income_ratio = min(2.0, float(r["monthly_income"]) / (float(r["min_monthly_income"]) or 25000.0))
            income_score = 35.0 * (income_ratio / 2.0)
            score_headroom = min(1.0, (int(r["credit_score"]) - int(r["min_credit_score"])) / 150.0)
            score_pts = 25.0 * max(0.0, score_headroom)
            total_fit = min(99.0, max(55.0, rate_score + income_score + score_pts))

            users_map[uid]["candidates"].append({
                "product_db_id": r["product_db_id"],
                "provider_name": r["provider_name"],
                "product_name": r["product_name"],
                "interest_rate": float(r["interest_rate"]),
                "match_score": round(total_fit, 2)
            })

        # Fetch cache
        cur.execute("SELECT archetype_key, rationale_template FROM archetype_rationales_cache;")
        cache_rows = cur.fetchall()
        cache_map = {c["archetype_key"]: c["rationale_template"] for c in cache_rows}

        # Stage 3: Fingerprinting & Hydration
        matches_to_insert = []
        for uid, u in users_map.items():
            u["candidates"].sort(key=lambda x: x["match_score"], reverse=True)
            top_offers = u["candidates"][:2]

            credit_tier = "PRIME" if u["credit_score"] >= 750 else ("NEAR_PRIME" if u["credit_score"] >= 675 else "FAIR")
            income_bracket = "HIGH" if u["monthly_income"] >= 75000 else ("MID" if u["monthly_income"] >= 40000 else "ENTRY")
            emp = u["employment_status"].lower()
            prod_key = "_".join(sorted([o["provider_name"].replace(" ", "") for o in top_offers]))
            archetype_key = f"{credit_tier}_{emp}_{income_bracket}_{prod_key}"

            template = cache_map.get(archetype_key)
            if not template:
                template = f"Hi {{user_name}}, as a {emp} professional with a {credit_tier.lower()} credit profile, you qualify for pre-approved terms with {{matched_products}} starting at {{top_rate}}% p.a."

            for offer in top_offers:
                reason = template.replace("{{user_name}}", uid).replace("{user_name}", uid)\
                                 .replace("{{top_rate}}", str(offer["interest_rate"])).replace("{top_rate}", str(offer["interest_rate"]))\
                                 .replace("{{matched_products}}", offer["product_name"]).replace("{matched_products}", offer["product_name"])
                matches_to_insert.append((
                    str(uuid.uuid4()),
                    job_id,
                    u["user_db_id"],
                    offer["product_db_id"],
                    offer["match_score"],
                    archetype_key,
                    reason,
                    1  # is_notified = True for local demo
                ))

        # Bulk insert matches
        if is_postgres_available():
            for m in matches_to_insert:
                cur.execute("""
                INSERT INTO matches (id, job_id, user_id, product_id, match_score, archetype_key, eligibility_reason, is_notified)
                VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s, %s, TRUE)
                ON CONFLICT (user_id, product_id, job_id) DO NOTHING;
                """, m[:7])
        else:
            for m in matches_to_insert:
                cur.execute("""
                INSERT OR IGNORE INTO matches (id, job_id, user_id, product_id, match_score, archetype_key, eligibility_reason, is_notified)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """, m)


@app.put("/local-upload/{job_id}/{filename}")
async def handle_direct_upload(job_id: str, filename: str, request: Request):
    """
    Simulates direct S3 PUT upload.
    Streams body bytes directly, performs validation, inserts into DB, and triggers matching funnel.
    """
    body_bytes = await request.body()
    if not body_bytes:
        raise HTTPException(status_code=400, detail="Empty payload.")

    text_stream = io.StringIO(body_bytes.decode("utf-8", errors="replace"))
    reader = csv.DictReader(text_stream)
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="Missing CSV headers.")

    total_rows = 0
    valid_rows = 0
    quarantined = []
    valid_users = []

    for idx, row in enumerate(reader, start=1):
        total_rows += 1
        normalized = {k.strip().lower().replace(" ", "_"): v.strip() for k, v in row.items() if k}
        uid = normalized.get("user_id") or normalized.get("id")
        email = normalized.get("email")
        income = sanitize_number(normalized.get("monthly_income") or normalized.get("income"))
        score = sanitize_number(normalized.get("credit_score") or normalized.get("cibil_score"))
        emp = (normalized.get("employment_status") or "employed").lower().replace("-", "_").replace(" ", "_")
        age = sanitize_number(normalized.get("age"))

        if not uid or not email or "@" not in email or income is None or score is None or age is None or not (300 <= score <= 900):
            quarantined.append((str(uuid.uuid4()), job_id, idx, json.dumps(row), "Validation failed"))
        else:
            valid_rows += 1
            valid_users.append((str(uuid.uuid4()), job_id, uid, email.lower(), round(income, 2), int(score), emp, int(age)))

    # Persist to database
    with get_db_connection() as conn:
        cur = conn.cursor()
        if is_postgres_available():
            cur.execute(
                "INSERT INTO ingestion_jobs (id, s3_key, file_name, total_rows, valid_rows, quarantined_rows, status) "
                "VALUES (%s::uuid, %s, %s, %s, %s, %s, 'COMPLETED');",
                (job_id, f"uploads/{job_id}/{filename}", filename, total_rows, valid_rows, len(quarantined))
            )
            for u in valid_users:
                cur.execute("INSERT INTO users (id, job_id, user_id, email, monthly_income, credit_score, employment_status, age) "
                            "VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s);", u)
        else:
            cur.execute(
                "INSERT OR REPLACE INTO ingestion_jobs (id, s3_key, file_name, total_rows, valid_rows, quarantined_rows, status) "
                "VALUES (?, ?, ?, ?, ?, ?, 'COMPLETED');",
                (job_id, f"uploads/{job_id}/{filename}", filename, total_rows, valid_rows, len(quarantined))
            )
            for u in valid_users:
                cur.execute("INSERT INTO users (id, job_id, user_id, email, monthly_income, credit_score, employment_status, age) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?);", u)

    # Execute matching funnel and auto-dispatch email notification via AWS SES
    try:
        execute_matching_funnel(job_id)
        user_email = valid_users[0][3] if valid_users else None
        print(f"[*] Auto-dispatching notification email to {user_email} via AWS SES...")
        dispatch_sample_notification(target_email=user_email)
    except Exception as e:
        print(f"[!] Funnel matching/notification warning: {e}")

    return {
        "job_id": job_id,
        "status": "COMPLETED",
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "quarantined_rows": len(quarantined)
    }


@app.get("/api/jobs/{job_id}")
def get_job_status(job_id: str):
    """Query ingestion job status and match statistics."""
    with get_db_connection() as conn:
        cur = conn.cursor()
        if is_postgres_available():
            cur.execute("SELECT * FROM ingestion_jobs WHERE id = %s;", (job_id,))
            job = cur.fetchone()
            if not job:
                raise HTTPException(status_code=404, detail="Job not found.")
            cur.execute("SELECT COUNT(*) AS match_count FROM matches WHERE job_id = %s;", (job_id,))
            match_res = cur.fetchone()
            cur.execute("SELECT COUNT(*) AS notified_count FROM matches WHERE job_id = %s AND is_notified = TRUE;", (job_id,))
            notified_res = cur.fetchone()
        else:
            cur.execute("SELECT * FROM ingestion_jobs WHERE id = ?;", (job_id,))
            job = cur.fetchone()
            if not job:
                raise HTTPException(status_code=404, detail="Job not found.")
            cur.execute("SELECT COUNT(*) AS match_count FROM matches WHERE job_id = ?;", (job_id,))
            match_res = cur.fetchone()
            cur.execute("SELECT COUNT(*) AS notified_count FROM matches WHERE job_id = ? AND is_notified = 1;", (job_id,))
            notified_res = cur.fetchone()

        return {
            "job": dict(job),
            "matches_found": match_res["match_count"] if match_res else 0,
            "notified_count": notified_res["notified_count"] if notified_res else 0
        }


@app.get("/api/stats")
def get_dashboard_stats():
    """Retrieve system-wide summary counts for the UI dashboard."""
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS total_users FROM users;")
        u_res = cur.fetchone()
        cur.execute("SELECT COUNT(*) AS total_products FROM loan_products WHERE is_active = 1 OR is_active = TRUE;")
        p_res = cur.fetchone()
        cur.execute("SELECT COUNT(*) AS total_matches FROM matches;")
        m_res = cur.fetchone()
        cur.execute("SELECT COUNT(*) AS total_cache_keys FROM archetype_rationales_cache;")
        c_res = cur.fetchone()

        return {
            "total_users": u_res["total_users"] if u_res else 0,
            "active_loan_products": p_res["total_products"] if p_res else 0,
            "total_matches_generated": m_res["total_matches"] if m_res else 0,
            "cached_archetypes": c_res["total_cache_keys"] if c_res else 0
        }


from fastapi.responses import HTMLResponse
from backend.send_notification_email import generate_email_html, dispatch_sample_notification


@app.get("/api/email-preview", response_class=HTMLResponse)
def preview_email(user_id: str = None):
    """Render the exact HTML pre-approval notification email generated by the pipeline."""
    with get_db_connection() as conn:
        cur = conn.cursor()
        if user_id:
            cur.execute("""
            SELECT m.id, m.match_score, m.eligibility_reason, p.provider_name, p.product_name, p.interest_rate, p.max_loan_amount, u.user_id
            FROM matches m
            JOIN users u ON u.id = m.user_id
            JOIN loan_products p ON p.id = m.product_id
            WHERE u.user_id = ?
            ORDER BY m.match_score DESC
            LIMIT 3;
            """, (user_id,))
        else:
            cur.execute("""
            SELECT m.id, m.match_score, m.eligibility_reason, p.provider_name, p.product_name, p.interest_rate, p.max_loan_amount, u.user_id
            FROM matches m
            JOIN users u ON u.id = m.user_id
            JOIN loan_products p ON p.id = m.product_id
            ORDER BY m.created_at DESC
            LIMIT 3;
            """)
        rows = [dict(r) for r in cur.fetchall()]

    if not rows:
        return HTMLResponse("<h3>No matches found in database. Please upload a CSV first to generate matches.</h3>")

    uid = rows[0]["user_id"]
    reason = rows[0]["eligibility_reason"]
    return HTMLResponse(generate_email_html(uid, reason, rows))


@app.post("/api/send-email")
def trigger_send_email(target_email: str = None):
    """Trigger dispatch of the matched loan offers to a specified test email inbox."""
    return dispatch_sample_notification(target_email)


# Mount documentation & diagrams static files
DOCS_DIR = Path(__file__).parent.parent / "docs"
if DOCS_DIR.exists():
    app.mount("/docs", StaticFiles(directory=str(DOCS_DIR), html=True), name="docs")

# Mount frontend static files
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    print("[*] Starting Local Development Server on http://localhost:8000...")
    uvicorn.run("backend.local_server:app", host="0.0.0.0", port=8000, reload=True)

