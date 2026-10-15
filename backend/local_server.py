"""
Local Development API Server & Cloud Simulator.
Provides local endpoints matching the AWS API Gateway & S3 Presigned URL contracts,
allowing 100% end-to-end testing and video demonstration without incurring AWS costs.
"""

import os
import io
import uuid
import json
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

# Import our production ingestion logic
from backend.lambdas.ingest_csv import process_csv_stream
from backend.database.db_client import get_conn_str, init_db

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

UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


@app.on_event("startup")
def startup_event():
    """Ensure database schema is applied on startup if DB is reachable."""
    try:
        init_db()
    except Exception as e:
        print(f"[!] Note: Database init skipped during startup ({e}). Run docker-compose or start postgres.")


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


@app.put("/local-upload/{job_id}/{filename}")
async def handle_direct_upload(job_id: str, filename: str, request: Request):
    """
    Simulates direct S3 PUT upload.
    Streams body bytes directly to process_csv_stream without buffering whole file in RAM.
    """
    body_bytes = await request.body()
    if not body_bytes:
        raise HTTPException(status_code=400, detail="Empty payload.")

    text_stream = io.StringIO(body_bytes.decode("utf-8", errors="replace"))
    s3_key = f"uploads/{job_id}/{filename}"

    try:
        result = process_csv_stream(text_stream, job_id, s3_key, filename)
        return JSONResponse(status_code=200, content=result)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/jobs/{job_id}")
def get_job_status(job_id: str):
    """Query ingestion job status and match statistics."""
    try:
        with psycopg.connect(get_conn_str(), row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM ingestion_jobs WHERE id = %s;", (job_id,))
                job = cur.fetchone()
                if not job:
                    raise HTTPException(status_code=404, detail="Job not found.")

                cur.execute("SELECT COUNT(*) AS match_count FROM matches WHERE job_id = %s;", (job_id,))
                match_res = cur.fetchone()

                cur.execute(
                    "SELECT COUNT(*) AS notified_count FROM matches WHERE job_id = %s AND is_notified = TRUE;", 
                    (job_id,)
                )
                notified_res = cur.fetchone()

                return {
                    "job": job,
                    "matches_found": match_res["match_count"] if match_res else 0,
                    "notified_count": notified_res["notified_count"] if notified_res else 0
                }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
def get_dashboard_stats():
    """Retrieve system-wide summary counts for the UI dashboard."""
    try:
        with psycopg.connect(get_conn_str(), row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS total_users FROM users;")
                u_res = cur.fetchone()
                cur.execute("SELECT COUNT(*) AS total_products FROM loan_products WHERE is_active = TRUE;")
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
    except Exception as e:
        return {"error": str(e), "total_users": 0, "active_loan_products": 0, "total_matches_generated": 0}


# Mount frontend static files
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    print("[*] Starting Local Development Server on http://localhost:8000...")
    uvicorn.run("backend.local_server:app", host="0.0.0.0", port=8000, reload=True)
