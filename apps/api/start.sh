#!/usr/bin/env bash
# Start the AI service backend reliably.
# Usage: ./start.sh [--port 8002] [--no-reload]

set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8002}"
RELOAD="--reload"
MAX_WAIT=15

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)    PORT="$2"; shift 2 ;;
    --no-reload) RELOAD=""; shift ;;
    *)         echo "Unknown arg: $1"; exit 1 ;;
  esac
done

# 1. Kill any existing process on the port (more aggressive)
echo "Checking for existing processes on port $PORT..."
EXISTING=$(lsof -ti :"$PORT" 2>/dev/null || true)
if [[ -n "$EXISTING" ]]; then
  echo "Killing existing process(es) on port $PORT: $EXISTING"
  echo "$EXISTING" | xargs kill -9 2>/dev/null || true
  sleep 2
fi

# Also kill any lingering uvicorn processes for this app
pkill -9 -f "uvicorn app.main:app" 2>/dev/null || true
sleep 1

# Double-check port is free
STILL_RUNNING=$(lsof -ti :"$PORT" 2>/dev/null || true)
if [[ -n "$STILL_RUNNING" ]]; then
  echo "Force killing stubborn processes: $STILL_RUNNING"
  echo "$STILL_RUNNING" | xargs kill -9 2>/dev/null || true
  sleep 2
fi

# 2. Ensure venv exists
if [[ ! -f ./venv/bin/python ]]; then
  echo "Error: virtualenv not found at ./venv"
  echo "Run: python3 -m venv venv && ./venv/bin/pip install -r requirements.txt"
  exit 1
fi

# 3. Start uvicorn with the venv Python (foreground - Ctrl+C to stop)
echo "Starting AI service on port $PORT..."
exec ./venv/bin/python -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "$PORT" \
  $RELOAD
