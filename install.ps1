# ==============================================================================
# Vanta Deep Research — One-Command Windows PowerShell Installer
# Usage: irm https://raw.githubusercontent.com/avirooppal/Vanta-Deep-Research-API/main/install.ps1 | iex
# ==============================================================================

$InstallDir = "$HOME\.vanta"

Write-Host ""
Write-Host "  __      __            _        " -ForegroundColor Cyan
Write-Host "  \ \    / /           | |       " -ForegroundColor Cyan
Write-Host "   \ \  / /_ _ _ __  __| |_ _    " -ForegroundColor Cyan
Write-Host "    \ \/ / _` | '_ \/ _` | _` |  " -ForegroundColor Cyan
Write-Host "     \  / (_| | | | | (_| | (_| |" -ForegroundColor Cyan
Write-Host "      \/ \__,_|_| |_|\__,_|\__,_|" -ForegroundColor Cyan
Write-Host ""
Write-Host " Installing Vanta Deep Research Console (Local)..." -ForegroundColor White
Write-Host ""

if (!(Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

if (Get-Command git -ErrorAction SilentlyContinue) {
    if (Test-Path "$InstallDir\.git") {
        Write-Host " Updating existing Vanta installation..." -ForegroundColor Yellow
        Push-Location $InstallDir
        git pull --quiet
        Pop-Location
    } else {
        Write-Host " Downloading Vanta via git..." -ForegroundColor Green
        git clone --depth 1 --quiet https://github.com/avirooppal/Vanta-Deep-Research-API.git $InstallDir
    }
} else {
    Write-Host " Downloading Vanta package..." -ForegroundColor Green
    $ZipPath = "$env:TEMP\vanta.zip"
    Invoke-WebRequest -Uri "https://github.com/avirooppal/Vanta-Deep-Research-API/archive/refs/heads/main.zip" -OutFile $ZipPath
    Expand-Archive -Path $ZipPath -DestinationPath "$env:TEMP\vanta_extracted" -Force
    Copy-Item -Path "$env:TEMP\vanta_extracted\Vanta-Deep-Research-API-main\*" -Destination $InstallDir -Recurse -Force
    Remove-Item $ZipPath, "$env:TEMP\vanta_extracted" -Recurse -Force
}

Set-Location $InstallDir

# Launch Vanta Console
if (Get-Command docker -ErrorAction SilentlyContinue) {
    Write-Host " Starting Vanta with Docker..." -ForegroundColor Green
    docker compose -f deploy/docker-compose.yml up -d
} elseif (Get-Command uv -ErrorAction SilentlyContinue) {
    Write-Host " Starting Vanta with uv..." -ForegroundColor Green
    Start-Process "uv" -ArgumentList "run uvicorn api.app:app --port 8000" -WindowStyle Hidden
} else {
    Write-Host " Docker Desktop is recommended. Please install Docker Desktop to run all services." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Vanta Local Console is live at: http://localhost:8000   " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

Start-Sleep -Seconds 2
Start-Process "http://localhost:8000"
