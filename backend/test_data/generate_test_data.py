"""
Test Data Generator for The Loan Eligibility Engine.
Generates realistic borrower CSVs conforming to the official assignment schema:
user_id, email, monthly_income, credit_score, employment_status, age
Includes boundary cases (prime, near-prime, subprime, self-employed) to test the funnel.
"""

import csv
import random
from pathlib import Path

DATA_DIR = Path(__file__).parent
DATA_DIR.mkdir(parents=True, exist_ok=True)


def generate_users_csv(filename: str = "users.csv", count: int = 250) -> Path:
    """Generate a realistic test dataset of borrower profiles."""
    filepath = DATA_DIR / filename
    
    first_names = ["Aarav", "Aditi", "Rahul", "Priya", "Vikram", "Sneha", "Rohan", "Ananya", "Karan", "Pooja"]
    last_names = ["Sharma", "Verma", "Patel", "Gupta", "Mehta", "Iyer", "Nair", "Kulkarni", "Singh", "Reddy"]
    employment_statuses = ["employed", "employed", "employed", "self_employed", "self_employed", "unemployed"]

    rows = []
    for i in range(1, count + 1):
        fn = random.choice(first_names)
        ln = random.choice(last_names)
        user_id = f"USR-{1000 + i}"
        email = f"{fn.lower()}.{ln.lower()}{i}@example.com"
        
        # Realistic Indian salary distribution (in INR)
        # 60% standard middle class (30k - 85k), 25% affluent (85k - 200k), 15% entry/low (18k - 30k)
        rand_bucket = random.random()
        if rand_bucket < 0.15:
            monthly_income = random.randint(18000, 29000)
        elif rand_bucket < 0.75:
            monthly_income = random.randint(30000, 85000)
        else:
            monthly_income = random.randint(85000, 220000)

        # Realistic CIBIL credit score distribution (300 - 850)
        # Weighted towards 650-790
        credit_score = int(random.gauss(710, 55))
        credit_score = max(550, min(850, credit_score))

        employment = random.choice(employment_statuses)
        age = random.randint(22, 59)

        rows.append([user_id, email, monthly_income, credit_score, employment, age])

    # Write to CSV
    with open(filepath, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["user_id", "email", "monthly_income", "credit_score", "employment_status", "age"])
        writer.writerows(rows)

    print(f"[+] Successfully generated {count} test users at {filepath}")
    return filepath


if __name__ == "__main__":
    generate_users_csv("users.csv", count=250)
