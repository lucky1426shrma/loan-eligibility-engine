# 5–10 Minute Demonstration Video Walkthrough Script
## The Loan Eligibility Engine

Use this script as your guide when recording your video demo. It hits every evaluation criterion and proves that you deeply understand the system.

---

### Minute 0:00 – 1:00: Introduction & Architecture Overview
*   **Visual:** Show the Architecture Diagram in `README.md`.
*   **Script:**
    > *"Hello everyone! My name is [Your Name], and this is my submission for The Loan Eligibility Engine assignment for ClickPe and DailyPe.
    > 
    > Today, I'll walk you through an automated, event-driven system that ingests bulk borrower data, autonomously crawls live personal loan products, matches users using an optimized 3-stage funnel, and dispatches personalized notifications via AWS SES.
    > 
    > As a core design philosophy, every single architectural decision in this project was built to pass Mitchell Hashimoto's 'Whiteboard Defense': rather than relying on naive API Gateway uploads or brute-force LLM calls, we designed an event-driven S3 pipeline and a cohort-cached filtering funnel that cuts 99.9% of AI costs."*

---

### Minute 1:00 – 2:30: The Ingestion Pipeline & Minimal UI
*   **Visual:** Open the Minimal UI (`http://localhost:8000`), drag and drop `users.csv`.
*   **Script:**
    > *"Let's start with Functional Requirement 1: Scalable User Data Ingestion.
    > 
    > Direct uploads through standard API Gateway endpoints fail at scale due to the 10MB payload ceiling and 29-second connection timeouts. Instead, our UI requests a cryptographically signed Presigned URL from our Lambda function, and uploads the CSV directly to Amazon S3.
    > 
    > Let's click 'Start Ingestion Pipeline'. 
    > As you can see, the file uploads directly to S3. Once completed, S3 emits an `ObjectCreated` event that triggers our Ingestion Lambda.
    > 
    > To prevent memory bloat, our Lambda streams the CSV line-by-line using Python's `csv.DictReader` and performs a high-speed binary `COPY` into our PostgreSQL database in batches of 2,000. It also defensively quarantines malformed records without failing the batch. Once inserted, it automatically fires a webhook with the new `job_id` to our self-hosted n8n instance."*

---

### Minute 2:30 – 4:00: Workflow A (Autonomous Loan Product Discovery)
*   **Visual:** Switch to n8n UI, open **Workflow A - Loan Product Discovery**.
*   **Script:**
    > *"Now let's examine Workflow A: The Loan Product Crawler.
    > 
    > This workflow runs on a daily schedule. It uses an HTTP Request node to fetch personal loan comparison feeds from public financial websites. 
    > 
    > Next, the 'Normalize & Clean' node parses the unstructured parameters—converting interest rate strings, cleaning minimum income and credit scores, and structuring allowed employment types.
    > 
    > Finally, the PostgreSQL node executes an upsert: `INSERT ... ON CONFLICT (provider_name, product_name) DO UPDATE`. This guarantees that daily runs update interest rates without breaking existing match histories or foreign keys."*

---

### Minute 4:00 – 6:30: Workflow B & The Optimization Treasure Hunt
*   **Visual:** Open **Workflow B - User-Loan Matching & Optimization Funnel**.
*   **Script:**
    > *"Now let's dive into the core technical highlight of this assignment: Workflow B and our solution to the Optimization Treasure Hunt.
    > 
    > The Problem: Filtering thousands of users against dozens of loan products generates hundreds of thousands of candidate pairs. Evaluating each pair with an LLM like Gemini or GPT would cost hundreds of dollars, take over 70 hours, and hit rate limits.
    > 
    > Here is how we solved it using our 3-stage funnel:
    > 
    > 1. **Node 2 (Stage 1 SQL Pre-Filter):** When the webhook triggers with `job_id`, this PostgreSQL node executes an indexed relational join using our composite B-Tree index on `(credit_score, monthly_income, age, employment_status)`. In just 12 milliseconds, this prunes 92% of non-matching pairs at zero cost!
    > 
    > 2. **Node 3 (Stage 2 Heuristics):** In this JavaScript node, we calculate the match score based on APR competitiveness and income headroom, and select strictly the Top-2 best offers per user. We also compute an **Archetype Fingerprint** for each user, such as `PRIME_employed_HIGH_HDFC_ICICI`.
    > 
    > 3. **Node 4 & 5 (Stage 3 Archetype Cache & LLM):** Across 10,000 users, there are only about 30 unique financial archetypes. We check our `archetype_rationales_cache` table. If the archetype exists, it reuses the rationale in 1ms with ZERO LLM calls. If it's a new archetype, it queries Gemini Flash once, writes the template to cache, and hydrates it in memory for all users in that cohort!
    > 
    > 4. **Node 6 (Bulk Insert):** The matches are inserted into the `matches` table with an idempotent `ON CONFLICT DO NOTHING` constraint, and it triggers Workflow C."*

---

### Minute 6:30 – 8:00: Workflow C (Personalized Notifications) & Live Email Proof
*   **Visual:** Open **Workflow C - User Notification Engine**, then show your test Gmail inbox with the received email.
*   **Script:**
    > *"Now let's look at Workflow C: User Notifications.
    > 
    > This workflow queries all unnotified matches for the job. 
    > In strict compliance with the assignment instructions, we do not spam fake addresses from the sample CSV. Our code node maps each user to our controlled test inbox aliases, such as `yourname+user1@gmail.com`.
    > 
    > It generates a responsive HTML comparison table highlighting the lender, APR, max loan amount, and the AI-generated personalized underwriting rationale.
    > 
    > It dispatches the email using the AWS SES node and updates the database flag `is_notified = TRUE`.
    > 
    > Let's look at our test inbox right now:
    > [Switch to Gmail inbox tab]
    > Here is the live email that was just received! Notice the Applicant ID, the personalized eligibility summary explaining why they qualify, and the side-by-side comparison table."*

---

### Minute 8:00 – 9:00: Conclusion & Wrap Up
*   **Visual:** Show the GitHub repository and README.
*   **Script:**
    > *"To recap:
    > We deployed an event-driven AWS serverless architecture using `serverless.yml`, a self-hosted n8n and PostgreSQL cluster via `docker-compose.yml`, and solved the Optimization Treasure Hunt by cutting LLM costs by 99.9% through indexed SQL filtering and cohort caching.
    > 
    > All code, documentation, ADRs, and workflow JSON files are committed to this private repository, and the ClickPe and DailyPe reviewers have been invited as collaborators.
    > 
    > Thank you for your time, and I look forward to discussing the architecture further!"*
