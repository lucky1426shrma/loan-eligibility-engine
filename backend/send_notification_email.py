"""
Notification Dispatcher Script.
Generates personalized HTML loan pre-approval emails and sends them to your test inbox
using either AWS SES (as specified in the assignment) or standard SMTP (e.g. Gmail App Password).
"""

import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, List
from dotenv import load_dotenv

from backend.database.db_client import get_db_connection, is_postgres_available

load_dotenv()

# Email Configuration from .env
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
SES_SOURCE_EMAIL = os.getenv("SES_SOURCE_EMAIL", "no-reply@clickpe.ai")
TEST_EMAIL_RECIPIENT = os.getenv("TEST_EMAIL_RECIPIENT", "yourname+test1@gmail.com")

# Resend API Configuration
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")



def generate_email_html(user_id: str, applicant_reason: str, offers: List[Dict[str, Any]]) -> str:
    """Build responsive HTML loan pre-approval email template."""
    offer_rows = "".join([
        f"""
        <tr style="border-bottom: 1px solid #e2e8f0;">
          <td style="padding: 12px; font-weight: bold; color: #1e293b;">{o['provider_name']}</td>
          <td style="padding: 12px; color: #475569;">{o['product_name']}</td>
          <td style="padding: 12px; font-weight: 600; color: #16a34a;">{o['interest_rate']}% p.a.</td>
          <td style="padding: 12px; color: #475569;">₹{int(o['max_loan_amount']):,}</td>
          <td style="padding: 12px;"><span style="background: #dcfce7; color: #15803d; padding: 4px 8px; border-radius: 9999px; font-size: 12px; font-weight: bold;">{o['match_score']}% Match</span></td>
        </tr>
        """ for o in offers
    ])

    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f8fafc; padding: 24px;">
      <div style="max-width: 640px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
        <div style="background: #2563eb; padding: 24px; color: #ffffff;">
          <h1 style="margin: 0; font-size: 22px;">Personal Loan Pre-Approval Notice</h1>
          <p style="margin: 6px 0 0 0; opacity: 0.9; font-size: 14px;">Tailored offers for Applicant ID: <strong>{user_id}</strong></p>
        </div>
        <div style="padding: 24px;">
          <div style="background: #eff6ff; border-left: 4px solid #3b82f6; padding: 16px; border-radius: 4px; margin-bottom: 24px;">
            <p style="margin: 0; font-size: 14px; color: #1e40af; line-height: 1.5;">
              <strong>Underwriting Summary:</strong> {applicant_reason}
            </p>
          </div>
          <h3 style="color: #0f172a; margin-top: 0;">Your Matched Loan Products:</h3>
          <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 14px;">
            <thead>
              <tr style="background: #f1f5f9; color: #475569;">
                <th style="padding: 10px;">Lender</th>
                <th style="padding: 10px;">Product</th>
                <th style="padding: 10px;">Rate</th>
                <th style="padding: 10px;">Max Amount</th>
                <th style="padding: 10px;">Fit</th>
              </tr>
            </thead>
            <tbody>{offer_rows}</tbody>
          </table>
          <div style="margin-top: 28px; text-align: center;">
            <a href="https://clickpe.ai/" style="background: #2563eb; color: #ffffff; padding: 12px 28px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 15px; display: inline-block;">Claim Pre-Approved Offer</a>
          </div>
        </div>
        <div style="background: #f8fafc; padding: 16px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0;">
          Sent via The Loan Eligibility Engine | ClickPe & DailyPe Assignment Demo
        </div>
      </div>
    </body>
    </html>
    """


def send_via_resend(recipient: str, subject: str, html_body: str) -> bool:
    """Send email using Resend Developer API."""
    import urllib.request
    import json

    if not RESEND_API_KEY:
        raise ValueError("RESEND_API_KEY is not configured in .env.")

    print(f"[*] Dispatching via Resend API to {recipient}...")
    payload = json.dumps({
        "from": RESEND_FROM_EMAIL,
        "to": [recipient],
        "subject": subject,
        "html": html_body
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "LoanEligibilityEngine/1.0"
        },
        method="POST"
    )

    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print(f"[+] Resend Message ID: {data.get('id')}")
        return True


def send_via_aws_ses(recipient: str, subject: str, html_body: str) -> bool:
    """Send email using Amazon SES API."""
    import boto3
    print(f"[*] Dispatching via AWS SES to {recipient}...")
    client = boto3.client("ses", region_name=AWS_REGION)
    response = client.send_email(
        Source=SES_SOURCE_EMAIL,
        Destination={"ToAddresses": [recipient]},
        Message={
            "Subject": {"Data": subject},
            "Body": {"Html": {"Data": html_body}}
        }
    )
    print(f"[+] SES Message ID: {response['MessageId']}")
    return True


def send_via_smtp(recipient: str, subject: str, html_body: str) -> bool:
    """Send email using standard SMTP (e.g. Gmail App Password)."""
    if not SMTP_USER or not SMTP_PASS:
        raise ValueError("SMTP_USER and SMTP_PASS must be set in .env for SMTP sending.")

    print(f"[*] Dispatching via SMTP ({SMTP_HOST}) to {recipient}...")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, recipient, msg.as_string())
    print(f"[+] Successfully delivered email via SMTP to {recipient}")
    return True


def dispatch_sample_notification(target_email: str = None) -> Dict[str, Any]:
    """Fetch the latest matched user from the DB and send a real notification email."""
    recipient = target_email or TEST_EMAIL_RECIPIENT
    
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
        SELECT m.id, m.match_score, m.eligibility_reason, p.provider_name, p.product_name, p.interest_rate, p.max_loan_amount, u.user_id, u.email
        FROM matches m
        JOIN users u ON u.id = m.user_id
        JOIN loan_products p ON p.id = m.product_id
        ORDER BY m.created_at DESC
        LIMIT 2;
        """)
        rows = [dict(r) for r in cur.fetchall()]

    if not rows:
        return {"status": "error", "message": "No matches found in database. Ingest a CSV first!"}

    user_id = rows[0]["user_id"]
    reason = rows[0]["eligibility_reason"]
    subject = f"Pre-Approved Personal Loan Offers for Applicant {user_id}"
    html_content = generate_email_html(user_id, reason, rows)

    sent = False
    provider = "None"
    error = None

    # Priority 1: Resend API (Fast, reliable developer email service)
    if RESEND_API_KEY:
        try:
            sent = send_via_resend(recipient, subject, html_content)
            provider = "Resend API"
        except Exception as e:
            error = f"Resend error: {e}"

    # Priority 2: AWS SES (Cloud production provider)
    if not sent and AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
        try:
            sent = send_via_aws_ses(recipient, subject, html_content)
            provider = "AWS SES"
        except Exception as e:
            error = f"AWS SES error: {e}"

    # Priority 3: SMTP (Standard TLS mail relay)
    if not sent and SMTP_USER and SMTP_PASS:
        try:
            sent = send_via_smtp(recipient, subject, html_content)
            provider = "SMTP"
        except Exception as e:
            error = f"SMTP error: {e}"

    return {
        "status": "sent" if sent else "simulated",
        "provider": provider,
        "recipient": recipient,
        "applicant_id": user_id,
        "subject": subject,
        "error": error,
        "html_preview_url": "http://localhost:8000/api/email-preview"
    }


if __name__ == "__main__":
    import sys
    to_addr = sys.argv[1] if len(sys.argv) > 1 else None
    result = dispatch_sample_notification(to_addr)
    print(result)
