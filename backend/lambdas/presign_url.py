"""
AWS Lambda Handler: S3 Presigned URL Generator.
Allows frontend to upload large CSV files directly to Amazon S3,
bypassing API Gateway payload limits (10MB) and Lambda timeout constraints.
"""

import os
import json
import uuid
from typing import Dict, Any
import boto3
from botocore.config import Config

# AWS Configuration
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "loan-eligibility-engine-uploads")
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
EXPIRATION_SECONDS = int(os.getenv("PRESIGNED_URL_EXPIRATION", "900"))  # 15 minutes

s3_client = boto3.client(
    "s3",
    region_name=AWS_REGION,
    config=Config(signature_version="s3v4")
)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Generate a presigned S3 PUT URL for uploading user CSVs.
    Enforces MIME type 'text/csv' and maximum expiration.
    """
    try:
        # Parse query params or body
        params = event.get("queryStringParameters") or {}
        raw_file_name = params.get("filename", "users.csv")
        
        # Security: sanitize filename and enforce .csv extension
        clean_file_name = os.path.basename(raw_file_name)
        if not clean_file_name.lower().endswith(".csv"):
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": "Invalid file type. Only .csv files are supported."})
            }

        job_id = str(uuid.uuid4())
        s3_key = f"uploads/{job_id}/{clean_file_name}"

        # Generate presigned PUT URL
        presigned_url = s3_client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": S3_BUCKET_NAME,
                "Key": s3_key,
                "ContentType": "text/csv",
                "Metadata": {
                    "job_id": job_id,
                    "original_filename": clean_file_name
                }
            },
            ExpiresIn=EXPIRATION_SECONDS,
            HttpMethod="PUT"
        )

        response_body = {
            "job_id": job_id,
            "s3_key": s3_key,
            "upload_url": presigned_url,
            "expires_in": EXPIRATION_SECONDS,
            "bucket": S3_BUCKET_NAME
        }

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization"
            },
            "body": json.dumps(response_body)
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "Failed to generate presigned URL", "details": str(e)})
        }
