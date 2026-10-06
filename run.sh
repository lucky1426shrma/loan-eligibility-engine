#!/usr/bin/env bash
set -e

echo "Starting Sunrise Clinic Backend & Frontend..."

# Start backend
python3 -m uvicorn backend.app.main:app --port 8000 &
BACKEND_PID=$!

echo "Backend running on http://localhost:8000 (PID: $BACKEND_PID)"

# Start frontend
cd frontend
npm run dev

kill $BACKEND_PID
