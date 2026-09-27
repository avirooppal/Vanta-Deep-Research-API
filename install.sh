#!/bin/bash
set -e

# ==============================================================================
# Vanta Deep Research — One-Command Local Console Installer
# Usage: curl -sSL https://raw.githubusercontent.com/avirooppal/Vanta-Deep-Research-API/main/install.sh | bash
# ==============================================================================

INSTALL_DIR="${HOME}/.vanta"

echo ""
echo "  ██╗   ██╗ █████╗ ███╗   ██╗████████╗ █████╗ "
echo "  ██║   ██║██╔══██╗████╗  ██║╚══██╔══╝██╔══██╗"
echo "  ██║   ██║███████║██╔██╗ ██║   ██║   ███████║"
echo "  ╚██╗ ██╔╝██╔══██║██║╚██╗██║   ██║   ██╔══██║"
echo "   ╚████╔╝ ██║  ██║██║ ╚████║   ██║   ██║  ██║"
echo "    ╚═══╝  ╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝"
echo ""
echo " Installing Vanta Deep Research Console (Local)..."
echo ""

# Ensure git or curl is available
if ! command -v git >/dev/null 2>&1 && ! command -v curl >/dev/null 2>&1; then
    echo "❌ Error: git or curl is required to install Vanta."
    exit 1
fi

mkdir -p "$INSTALL_DIR"

if [ -d "$INSTALL_DIR/.git" ]; then
    echo "🔄 Updating existing Vanta installation..."
    cd "$INSTALL_DIR" && git pull --quiet
else
    echo "⬇️ Downloading Vanta..."
    if command -v git >/dev/null 2>&1; then
        git clone --depth 1 --quiet https://github.com/avirooppal/Vanta-Deep-Research-API.git "$INSTALL_DIR"
    else
        curl -sSL https://github.com/avirooppal/Vanta-Deep-Research-API/archive/refs/heads/main.tar.gz | tar -xz -C "$INSTALL_DIR" --strip-components=1
    fi
fi

cd "$INSTALL_DIR"

# Launch Vanta
if command -v docker >/dev/null 2>&1; then
    echo "🚀 Starting Vanta with Docker..."
    docker compose -f deploy/docker-compose.yml up -d
elif command -v uv >/dev/null 2>&1; then
    echo "🚀 Starting Vanta with uv..."
    uv run uvicorn api.app:app --port 8000 &
else
    echo "⚠️ Docker is recommended. Please start Docker Desktop and run: cd ~/.vanta && docker compose -f deploy/docker-compose.yml up -d"
fi

echo ""
echo "=========================================================="
echo " ✅ Vanta Local Console is ready at: http://localhost:8000"
echo "=========================================================="
echo ""

# Open in default browser
if command -v open >/dev/null 2>&1; then
    open http://localhost:8000
elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open http://localhost:8000
fi
