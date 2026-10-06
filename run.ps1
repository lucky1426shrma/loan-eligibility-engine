# Windows PowerShell startup script
Write-Host "Starting Sunrise Clinic Backend & Frontend Services..." -ForegroundColor Cyan

# Start backend in a separate background job or window
$backendJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    python -m uvicorn backend.app.main:app --port 8000
}

Write-Host "Backend API running on http://localhost:8000" -ForegroundColor Green
Write-Host "Starting React Frontend on http://localhost:5173..." -ForegroundColor Green

Set-Location "$PSScriptRoot\frontend"
npm run dev
