# ==============================================================================
# The Loan Eligibility Engine - Easy Launch Runner
# Usage: .\run.ps1
# ==============================================================================

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Starting The Loan Eligibility Engine Local Server       " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# Check if Python is installed
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[!] Error: Python 3 is not found in PATH." -ForegroundColor Red
    Exit 1
}

# Install dependencies if needed
Write-Host "[*] Checking Python dependencies..." -ForegroundColor Yellow
pip install -r backend/requirements.txt --quiet

# Launch the server
Write-Host "[+] Launching FastAPI + Static UI Server on http://localhost:8000 ..." -ForegroundColor Green
Write-Host "    Press CTRL+C anytime to stop." -ForegroundColor Gray
python -m backend.local_server
