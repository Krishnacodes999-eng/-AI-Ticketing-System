#!/bin/bash
# OrbitDesk — AI Ticketing System — Quick Start

echo "==================================="
echo " OrbitDesk AI Ticketing System"
echo "==================================="

# Check for API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo ""
  echo "⚠  ANTHROPIC_API_KEY not set."
  echo "   export ANTHROPIC_API_KEY=sk-ant-..."
  echo ""
fi

echo ""
echo "▸ Starting backend (FastAPI on :8000)..."
cd backend
pip install -r requirements.txt -q
python main.py &
BACKEND_PID=$!

sleep 2

echo "▸ Starting frontend (React on :3000)..."
cd ../frontend
npm install -q
npm start &
FRONTEND_PID=$!

echo ""
echo "✓ OrbitDesk running at http://localhost:3000"
echo "  API docs:  http://localhost:8000/docs"
echo ""
echo "  Press Ctrl+C to stop."

trap "kill $BACKEND_PID $FRONTEND_PID" EXIT
wait
