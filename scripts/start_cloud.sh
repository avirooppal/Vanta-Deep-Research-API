#!/bin/sh

# ==============================================================================
# Vanta Deep Research — Cloud Deployment Entrypoint
# Supports Render, Railway, Fly.io, Cloud Run, AWS ECS, and Docker VPS.
# ==============================================================================

PORT="${PORT:-8000}"
WEB_CONCURRENCY="${WEB_CONCURRENCY:-1}"
SINGLE_CONTAINER_MODE="${SINGLE_CONTAINER_MODE:-true}"

echo "=========================================="
echo " Starting Vanta Deep Research API (Cloud) "
echo " Environment: ${ENVIRONMENT:-production} "
echo " Listening on Port: ${PORT}              "
echo " Single Container Mode: ${SINGLE_CONTAINER_MODE} "
echo "=========================================="

# 1. Run database schema migrations
echo "[1/3] Running database schema migrations..."
python scripts/migrate.py || echo "⚠️ Database migrations skipped or failed; continuing server startup."

# 2. Start embedded ARQ worker if single-container mode is enabled
if [ "$SINGLE_CONTAINER_MODE" = "true" ] || [ "$SINGLE_CONTAINER_MODE" = "1" ]; then
  echo "[2/3] Starting embedded ARQ background worker..."
  python -m arq core.queue.worker.WorkerSettings &
fi

# 3. Exec FastAPI server with proxy headers
echo "[3/3] Launching Uvicorn ASGI server on port ${PORT}..."
exec uvicorn api.app:app \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --proxy-headers \
  --forwarded-allow-ips="*" \
  --workers "${WEB_CONCURRENCY}"
