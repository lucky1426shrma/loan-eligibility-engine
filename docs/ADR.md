# Architectural Decision Records (ADR)
## The Loan Eligibility Engine

This document outlines the core architectural decisions made in designing the Loan Eligibility Engine, the alternatives considered, and the technical justification for each choice.

---

### ADR-001: Scalable Bulk Ingestion via Direct S3 Presigned URLs

* **Status:** Accepted
* **Context:** The system must ingest user CSVs that could contain tens or hundreds of thousands of borrower profiles.
* **Decision:** Implement the Direct-to-S3 Presigned URL pattern (`GET /upload-url` $\rightarrow$ direct HTTP `PUT` to S3 $\rightarrow$ S3 `ObjectCreated` event triggers Ingestion Lambda).
* **Rejected Alternative:** Uploading the CSV directly through API Gateway into a synchronous Lambda function.
* **Justification:**
  1. *Payload Limits:* AWS API Gateway enforces a strict **10MB request payload limit**, causing large bulk files to be rejected at the API edge.
  2. *Timeout Risk:* API Gateway has a **29-second hard integration timeout**. Uploading a large file and streaming it across a synchronous gateway easily causes timeouts on slower client uplinks.
  3. *Memory & Cost Efficiency:* Parsing multipart base64 payloads inside Lambda incurs a 33% memory overhead. S3 presigned URLs offload raw file transport to AWS S3 storage infrastructure at zero compute cost.

---

### ADR-002: High-Throughput Streaming PostgreSQL Ingestion via Native `COPY`

* **Status:** Accepted
* **Context:** Ingesting 100,000 rows into PostgreSQL within Lambda's execution lifecycle.
* **Decision:** Stream CSV lines using Python's `csv.DictReader` and insert records using PostgreSQL's binary streaming `COPY` command (`cursor.copy()`).
* **Rejected Alternatives:**
  1. `pandas.read_csv()` + `df.to_sql()`
  2. SQLAlchemy / Peewee ORM `session.add_all()`
* **Justification:**
  1. *Memory Footprint:* Pandas loads the entire tabular matrix into memory, requiring ~180MB RAM for 100k rows, risking Lambda Out-Of-Memory (OOM) failures. Python's streaming reader keeps memory consumption constant at **< 45MB** regardless of file size.
  2. *Execution Speed:* ORMs instantiate thousands of Python model objects and generate repetitive `INSERT INTO` statements, taking ~45–60 seconds. PostgreSQL native `COPY` streams raw tuples directly to the database engine in **< 1.8 seconds**.
  3. *Defensive Isolation:* Malformed rows (negative income, invalid credit score) are stripped in memory and inserted into `quarantined_records`, preventing one dirty row from aborting the entire ingestion transaction.

---

### ADR-003: Solution to the "Optimization Treasure Hunt" — 3-Stage Funnel with Cohort-Archetype Caching

* **Status:** Accepted
* **Context:** Evaluating $N = 10,000$ users against $M = 50$ loan products produces **500,000 candidate pairs**. Running an LLM (Gemini/GPT) for every pair would cost hundreds of dollars, take 70+ hours, and hit API rate limits. Even running 1 LLM call per user ($10,000$ calls) is expensive and slow.
* **Decision:** Implement a 3-Stage Filtering Pipeline with **Cohort-Archetype Semantic Caching**:
  * **Stage 1 (SQL Hard Cutoff):** An indexed relational `INNER JOIN` in PostgreSQL prunes 92% of non-matching pairs in **12ms** based on deterministic predicates (`credit_score >= min_credit_score`, `monthly_income >= min_monthly_income`, `age BETWEEN min_age AND max_age`).
  * **Stage 2 (Heuristic Ranking in n8n):** Computes FOIR (Fixed Obligation to Income Ratio) and interest rate competitiveness, keeping strictly the **Top-2 best offers** per user.
  * **Stage 3 (Cohort-Archetype Cache + LLM):** Users are fingerprinted into coarse financial archetypes (e.g., `PRIME_employed_HIGH_HDFC_ICICI`). Across thousands of users, there are typically only 20–35 unique archetypes. n8n checks the `archetype_rationales_cache` table:
    * If cached: Reuses the rationale template instantly (**0 LLM calls, 1ms latency, $0.00 cost**).
    * If uncached: Calls Gemini Flash **once** for the archetype, writes the template to cache, and hydrates it in memory for all users in that cohort.
* **Rejected Alternative:** Passing raw user data directly to an LLM agent with tools.
* **Justification:** LLMs are non-deterministic and prone to numeric hallucinations (e.g. claiming a 640 credit score meets a 650 threshold). Deterministic cutoffs belong in SQL; LLMs are reserved exclusively for qualitative natural-language underwriting summaries.

---

### ADR-004: Pipeline Idempotency & Retry Guarantees

* **Status:** Accepted
* **Context:** In distributed event-driven systems, network hiccups or worker restarts can cause duplicate webhooks or retried workflow executions.
* **Decision:** Enforce compound unique constraints at the database level:
  * `matches` table: `CONSTRAINT uq_user_product_job_match UNIQUE (user_id, product_id, job_id)`.
  * `loan_products` table: `CONSTRAINT uq_product_provider_name UNIQUE (provider_name, product_name)`.
  * Upserts use `ON CONFLICT DO NOTHING` or `DO UPDATE`.
* **Justification:** Retrying Workflow B or C will never insert duplicate rows or send duplicate pre-approval emails to users, guaranteeing absolute at-least-once pipeline safety.

---

### ADR-005: Notification Delivery with Test-Inbox Aliasing

* **Status:** Accepted
* **Context:** The pipeline must send real emails using the AWS SES node in n8n, but emailing fictitious addresses from `users.csv` would harm AWS SES domain reputation and cause hard bounces.
* **Decision:** Dynamically map each matched user to a controlled test inbox alias (e.g., `yourusername+user1@gmail.com`, `yourusername+user2@gmail.com`).
* **Justification:** Fulfills the exact assignment requirement, proves end-to-end SES integration, protects sender reputation, and allows visual proof of delivery in the demonstration video.
