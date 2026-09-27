@echo off
echo ===================================================
echo   Starting Vanta Deep Research Console (Local)
echo ===================================================
echo.

REM Check if docker is installed
where docker >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo Starting Vanta with Docker...
    docker compose -f deploy/docker-compose.yml up -d
    echo.
    echo ===================================================
    echo  Vanta Local Console is live at: http://localhost:8000
    echo ===================================================
    timeout /t 2 >nul
    start http://localhost:8000
    exit /b 0
)

REM Fallback to local python uv if docker is not running
where uv >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo Docker not found, launching with uv...
    start "Vanta API" uv run uvicorn api.app:app --port 8000
    timeout /t 2 >nul
    start http://localhost:8000
    exit /b 0
)

echo [ERROR] Neither Docker nor uv was found. Please install Docker Desktop to run Vanta locally.
pause
