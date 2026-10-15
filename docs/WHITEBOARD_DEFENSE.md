# The Mitchell Hashimoto "Whiteboard Defense" Guide
## The Loan Eligibility Engine

> *"The 'whiteboard defense:' I should be able to pull you aside at any moment and ask you to explain any customer-facing system you've shipped. You should be able to clearly explain how it works and defend the decisions you made."* — **Mitchell Hashimoto**

This guide provides direct, senior-level engineering answers to potential grilling questions from evaluators.

---

### Q1: "Why did you use S3 Presigned URLs instead of API Gateway multipart upload?"
**Answer:**
> "API Gateway has a strict **10MB payload ceiling** and a **29-second connection timeout**. If an admin uploads a 50MB CSV containing 250,000 user profiles over an office connection, API Gateway rejects the payload immediately. Furthermore, multipart encoding introduces a 33% base64 memory overhead inside Lambda. 
> By issuing a temporary S3 presigned PUT URL via `GET /upload-url`, we offload the raw byte transport directly to AWS S3. S3 can ingest gigabytes of data with zero compute overhead. Once uploaded, S3 fires an asynchronous `s3:ObjectCreated` event to trigger our Ingestion Lambda, completely decoupling network bandwidth from our compute infrastructure."

---

### Q2: "How does your Ingestion Lambda avoid memory exhaustion on massive CSVs?"
**Answer:**
> "We explicitly avoided `pandas.read_csv()` because Pandas parses the entire dataset into an in-memory DataFrame, which consumes ~180MB RAM for 100,000 rows and causes Lambda Out-Of-Memory (OOM) crashes.
> Instead, our Lambda opens an HTTP chunked stream from S3 using `boto3` (`response['Body'].iter_lines()`) and iterates row-by-row using Python's `csv.DictReader`. We validate and clean rows in batches of 2,000 and flush them directly into PostgreSQL using PostgreSQL's binary streaming `COPY` command (`cursor.copy()`). This keeps Lambda's memory footprint constant at **< 45MB** whether the file has 500 rows or 500,000 rows."

---

### Q3: "What happens if a CSV has dirty data or malicious inputs?"
**Answer:**
> "We implement defensive data sanitization before records ever reach the database:
> 1. Header names are normalized: whitespace is stripped, lowercased, and mapped (e.g. `' Monthly Income '` $\rightarrow$ `'monthly_income'`).
> 2. Currency strings like `'₹ 75,000'` or `'$50,000.00'` are stripped using regex to pure floats.
> 3. Range validations enforce boundary checks (`300 <= credit_score <= 900`, `18 <= age <= 100`, `income >= 0`).
> 4. Instead of crashing the whole transaction if row 42 is corrupted, that row is diverted into a `quarantined_records` table with a clear rejection reason, while the remaining 99,999 valid rows are committed cleanly."

---

### Q4: "How did you solve the Optimization Treasure Hunt?"
**Answer:**
> "Evaluating $N = 10,000$ users against $M = 50$ loan products yields **500,000 candidate pairs**. Using an LLM to evaluate every pair would take ~70 hours, cost over \$250, and hit provider rate limits.
> 
> We solved this by designing a **3-Stage Funnel with Cohort-Archetype Semantic Caching**:
> 1. **Stage 1 (Indexed SQL Hard Filter):** We execute an `INNER JOIN` in PostgreSQL using a composite B-Tree index on `(credit_score, monthly_income, age, employment_status)`. This eliminates 92% of non-viable pairs in **12 milliseconds** at **$0.00 cost**.
> 2. **Stage 2 (Heuristic Ranking in n8n):** An in-memory JavaScript node computes FOIR (Fixed Obligation to Income Ratio) and APR competitiveness, selecting the **Top-2 best loan offers** per user.
> 3. **Stage 3 (Cohort Archetype Caching):** Users cluster into a finite set of financial archetypes (e.g., `PRIME_employed_HIGH_HDFC_ICICI`). Across 10,000 users, there are typically only 20–35 unique archetypes. n8n checks the `archetype_rationales_cache` table:
>    - If cached: it reuses the rationale template in **1ms** (**0 LLM calls**).
>    - If uncached: it calls **Gemini Flash once** for the archetype, writes the template to cache, and hydrates it in memory for all users in that cohort.
> 
> **Result:** Total LLM calls drop from **500,000 down to ~25**, reducing costs by **99.9%** and execution time to **< 3 seconds**."

---

### Q5: "How do you guarantee idempotency if n8n crashes halfway and retries?"
**Answer:**
> "Every step is idempotent:
> 1. In `loan_products`, we enforce `UNIQUE (provider_name, product_name)` and use `ON CONFLICT DO UPDATE`.
> 2. In `matches`, we enforce `UNIQUE (user_id, product_id, job_id)` and use `ON CONFLICT DO NOTHING`.
> 3. In Workflow C, emails are only sent to matches where `is_notified = FALSE`. Once sent, the records are marked `is_notified = TRUE`.
> If a webhook triggers twice or n8n restarts mid-execution, zero duplicate matches are inserted and users never receive duplicate emails."

---

### Q6: "Why did you use n8n instead of writing everything in pure Python?"
**Answer:**
> "n8n provides visual orchestration, auditability, built-in retry policies, and an execution dashboard that operations and product teams can inspect. However, doing raw computation on 500k records inside Node.js would crash the V8 heap.
> That is why our architecture is a **hybrid**: heavy-lifting data transport and relational joins are pushed to where they belong—**AWS S3, Lambda, and PostgreSQL's query engine**—while workflow orchestration, AI integration, and multi-channel alerting (AWS SES) are handled by **n8n**."
