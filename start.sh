#!/bin/sh
set -e

echo "==================================================="
echo "  Starting Vanta Deep Research Console (Local)     "
echo "==================================================="
echo ""

if command -v docker >/dev/null 2>&1; then
    echo "Starting Vanta with Docker..."
    docker compose -f deploy/docker-compose.yml up -d
    echo ""
    echo "==================================================="
    echo " Vanta Local Console is live at: http://localhost:8000"
    echo "==================================================="
    if command -v open >/dev/null 2>&1; then
        open http://localhost:8000
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open http://localhost:8000
    fi
    exit 0
fi

if command -v uv >/dev/null 2>&1; then
    echo "Docker not found, launching with uv..."
    uv run uvicorn api.app:app --port 8000 &
    sleep 2
    if command -v open >/dev/null 2>&1; then
        open http://localhost:8000
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open http://localhost:8000
    fi
    exit 0
fi

echo "[ERROR] Please install Docker Desktop to run Vanta locally."
exit 1
