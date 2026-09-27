#!/bin/sh
set -e

# ==============================================================================
# Vanta Deep Research — Cloud Deployment Entrypoint
# Supports Render, Railway, Fly.io, Cloud Run, AWS ECS, and Docker VPS.
# ==============================================================================

PORT="${PORT:-8000}"
WEB_CONCURRENCY="${WEB_CONCURRENCY:-2}"
SINGLE_CONTAINER_MODE="${SINGLE_CONTAINER_MODE:-true}"

echo "=========================================="
echo " Starting Vanta Deep Research API (Cloud) "
echo " Environment: ${ENVIRONMENT:-production} "
echo " Listening on Port: ${PORT}              "
echo " Single Container Mode: ${SINGLE_CONTAINER_MODE} "
echo "=========================================="

# 1. Run database migrations to ensure schema is up-to-date
echo "[1/3] Running database schema migrations..."
python scripts/migrate.py || {
  echo "⚠️ Warning: Database migrations failed or database is not reachable yet."
  echo "Will continue starting API server."
}

# 2. Start embedded ARQ worker if single-container mode is enabled
WORKER_PID=""
if [ "$SINGLE_CONTAINER_MODE" = "true" ] || [ "$SINGLE_CONTAINER_MODE" = "1" ]; then
  echo "[2/3] Starting embedded ARQ background worker..."
  python -m arq core.queue.worker.WorkerSettings &
  WORKER_PID=$!
  echo "ARQ Worker started with PID: ${WORKER_PID}"
else
  echo "[2/3] Standalone worker mode: skipping embedded worker."
fi

# Clean shutdown handler
cleanup() {
  echo "Received termination signal. Shutting down gracefully..."
  if [ -n "$WORKER_PID" ]; then
    kill -TERM "$WORKER_PID" 2>/dev/null || true
  fi
  exit 0
}

trap cleanup SIGINT SIGTERM

# 3. Start FastAPI server with proxy headers for cloud reverse proxies
echo "[3/3] Launching Uvicorn ASGI server..."
uvicorn api.app:app \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --proxy-headers \
  --forwarded-allow-ips="*" \
  --workers "${WEB_CONCURRENCY}" &

UVICORN_PID=$!

wait "$UVICORN_PID"
