-- ==============================================================================
-- The Loan Eligibility Engine - Initial Loan Products Seed Data
-- Provides realistic baseline personal loan products from top Indian lenders.
-- Workflow A (Web Crawler) autonomously discovers and updates these over time.
-- ==============================================================================

INSERT INTO loan_products (
    provider_name, 
    product_name, 
    interest_rate, 
    min_credit_score, 
    min_monthly_income, 
    min_age, 
    max_age, 
    allowed_employment_statuses, 
    processing_fee_pct, 
    max_loan_amount, 
    source_url
) VALUES 
(
    'HDFC Bank',
    'Personal Loan for Salaried',
    10.50,
    720,
    50000.00,
    21,
    60,
    ARRAY['employed'],
    1.00,
    4000000.00,
    'https://www.hdfcbank.com/personal/borrow/popular-loans/personal-loan'
),
(
    'ICICI Bank',
    'Instant Personal Loan',
    10.85,
    700,
    35000.00,
    23,
    58,
    ARRAY['employed', 'self_employed'],
    1.25,
    5000000.00,
    'https://www.icicibank.com/personal-banking/loans/personal-loan'
),
(
    'State Bank of India',
    'SBI Xpress Credit',
    11.15,
    675,
    30000.00,
    21,
    60,
    ARRAY['employed'],
    0.75,
    2000000.00,
    'https://sbi.co.in/web/personal-banking/loans/personal-loans'
),
(
    'Axis Bank',
    'Quick Personal Loan',
    10.75,
    710,
    40000.00,
    21,
    60,
    ARRAY['employed', 'self_employed'],
    1.50,
    4000000.00,
    'https://www.axisbank.com/retail/loans/personal-loan'
),
(
    'Bajaj Finserv',
    'Flexi Personal Loan',
    12.50,
    650,
    25000.00,
    21,
    65,
    ARRAY['employed', 'self_employed'],
    2.00,
    3500000.00,
    'https://www.bajajfinserv.in/personal-loan'
),
(
    'Kotak Mahindra Bank',
    'Kotak Smart Personal Loan',
    10.99,
    730,
    45000.00,
    21,
    58,
    ARRAY['employed'],
    1.00,
    2500000.00,
    'https://www.kotak.com/en/personal-banking/loans/personal-loan.html'
),
(
    'Tata Capital',
    'Customized Personal Loan',
    11.75,
    660,
    28000.00,
    21,
    65,
    ARRAY['employed', 'self_employed'],
    1.50,
    3500000.00,
    'https://www.tatacapital.com/personal-loan.html'
)
ON CONFLICT (provider_name, product_name) 
DO UPDATE SET 
    interest_rate = EXCLUDED.interest_rate,
    min_credit_score = EXCLUDED.min_credit_score,
    min_monthly_income = EXCLUDED.min_monthly_income,
    last_crawled_at = NOW();

-- Also pre-seed a couple of common archetypes to demonstrate zero-LLM cache hits during cold starts!
INSERT INTO archetype_rationales_cache (
    archetype_key,
    credit_tier,
    employment_type,
    income_bracket,
    matched_products,
    rationale_template
) VALUES 
(
    'PRIME_employed_HIGH_HDFCBank_ICICIBank',
    'PRIME',
    'employed',
    'HIGH',
    'HDFC Bank Personal Loan for Salaried, ICICI Bank Instant Personal Loan',
    'Hi {{user_name}}, as a salaried professional with a prime credit score, you qualify for top-tier rates starting at {{top_rate}}% p.a. HDFC provides minimal documentation, while ICICI offers instant 24-hour fund disbursement.'
),
(
    'NEAR_PRIME_employed_MID_BajajFinserv_SBISBIXpressCredit',
    'NEAR_PRIME',
    'employed',
    'MID',
    'Bajaj Finserv Flexi Personal Loan, State Bank of India SBI Xpress Credit',
    'Hi {{user_name}}, your stable salaried income places you in SBI and Bajaj Finserv''s flexible personal loan bracket. You qualify with an estimated starting rate of {{top_rate}}% p.a. and high approval certainty.'
)
ON CONFLICT (archetype_key) DO NOTHING;
