-- ==============================================================================
-- The Loan Eligibility Engine - PostgreSQL DDL Schema
-- Optimized for high-throughput streaming bulk inserts, sub-millisecond joins,
-- and idempotent pipeline execution.
-- ==============================================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. INGESTION JOBS TABLE
-- Tracks the lifecycle of every bulk CSV upload event from S3.
CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    s3_key VARCHAR(255) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    total_rows INT DEFAULT 0,
    valid_rows INT DEFAULT 0,
    quarantined_rows INT DEFAULT 0,
    status VARCHAR(50) DEFAULT 'PENDING', -- 'PENDING', 'PROCESSING', 'COMPLETED', 'FAILED'
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_status ON ingestion_jobs (status, created_at DESC);

-- 2. QUARANTINED RECORDS TABLE (DEFENSIVE DATA HANDLING)
-- Prevents dirty rows from crashing bulk ingestion while preserving bad rows for audit.
CREATE TABLE IF NOT EXISTS quarantined_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES ingestion_jobs(id) ON DELETE CASCADE,
    row_number INT,
    raw_data JSONB,
    rejection_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quarantined_job_id ON quarantined_records (job_id);

-- 3. USERS TABLE
-- Persists valid borrower profiles ingested from bulk CSV.
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES ingestion_jobs(id) ON DELETE SET NULL,
    user_id VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    monthly_income NUMERIC(12, 2) NOT NULL,
    credit_score INT NOT NULL,
    employment_status VARCHAR(50) NOT NULL, -- 'employed', 'self_employed', etc.
    age INT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Crucial composite B-Tree index for Stage 1 SQL Pre-Filtering:
-- Covers the exact predicate in the matching join query.
CREATE INDEX IF NOT EXISTS idx_users_matching_predicate 
    ON users (credit_score, monthly_income, age, employment_status);

CREATE INDEX IF NOT EXISTS idx_users_job_id ON users (job_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);

-- 4. LOAN PRODUCTS TABLE
-- Populated and refreshed autonomously by Workflow A (Web Crawler).
CREATE TABLE IF NOT EXISTS loan_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_name VARCHAR(150) NOT NULL,
    product_name VARCHAR(200) NOT NULL,
    interest_rate NUMERIC(5, 2) NOT NULL,
    min_credit_score INT NOT NULL DEFAULT 600,
    min_monthly_income NUMERIC(12, 2) NOT NULL DEFAULT 0,
    min_age INT NOT NULL DEFAULT 21,
    max_age INT NOT NULL DEFAULT 65,
    allowed_employment_statuses TEXT[] DEFAULT ARRAY['employed', 'self_employed'],
    processing_fee_pct NUMERIC(4, 2) DEFAULT 1.0,
    max_loan_amount NUMERIC(14, 2) DEFAULT 2500000,
    source_url VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    last_crawled_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT uq_product_provider_name UNIQUE (provider_name, product_name)
);

CREATE INDEX IF NOT EXISTS idx_products_active_criteria 
    ON loan_products (is_active, min_credit_score, min_monthly_income);

-- 5. ARCHETYPE RATIONALES CACHE TABLE (THE OPTIMIZATION TREASURE HUNT)
-- Stores reusable LLM-generated qualitative underwriting pitches per financial cohort.
-- Eliminates 99.9% of LLM calls at scale (100k users -> ~35 LLM calls).
CREATE TABLE IF NOT EXISTS archetype_rationales_cache (
    archetype_key VARCHAR(150) PRIMARY KEY, -- e.g. "PRIME_employed_HIGH_HDFC_ICICI"
    credit_tier VARCHAR(50) NOT NULL,
    employment_type VARCHAR(50) NOT NULL,
    income_bracket VARCHAR(50) NOT NULL,
    matched_products TEXT NOT NULL,
    rationale_template TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. MATCHES TABLE
-- Stores pre-filtered, scored, and AI-enriched user-to-product matches.
CREATE TABLE IF NOT EXISTS matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES ingestion_jobs(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    product_id UUID REFERENCES loan_products(id) ON DELETE CASCADE,
    match_score NUMERIC(5, 2) NOT NULL,
    archetype_key VARCHAR(150),
    eligibility_reason TEXT,
    is_notified BOOLEAN DEFAULT FALSE,
    notified_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    -- Enforces absolute idempotency across pipeline retries:
    CONSTRAINT uq_user_product_job_match UNIQUE (user_id, product_id, job_id)
);

CREATE INDEX IF NOT EXISTS idx_matches_notification_queue 
    ON matches (is_notified, job_id) 
    WHERE is_notified = FALSE;

CREATE INDEX IF NOT EXISTS idx_matches_user_id ON matches (user_id);
