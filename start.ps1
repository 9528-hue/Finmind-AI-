# Start the complete local FINMIND AI website.
# The browser uses one origin (localhost:3000); Next.js proxies API calls to
# FastAPI, which persists data in the configured database.

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "finmind-ai"
$pythonExe = Join-Path $backend "venv\Scripts\python.exe"
$websiteUrl = "http://localhost:3000"
$apiUrl = "http://127.0.0.1:8000"

function Test-PortListening([int]$Port) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $client.Connect("127.0.0.1", $Port)
        return $true
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Test-BackendReady {
    try {
        $health = Invoke-RestMethod -Uri "$apiUrl/health" -TimeoutSec 5
        return $health.status -eq "ok" -and $health.database -eq "connected"
    } catch {
        return $false
    }
}

function Test-WebsiteReady {
    try {
        $health = Invoke-RestMethod -Uri "$websiteUrl/api/health" -TimeoutSec 5
        return $health.status -eq "ok" -and $health.database -eq "connected"
    } catch {
        return $false
    }
}

Write-Host ""
Write-Host "  FINMIND AI - Full website startup" -ForegroundColor Cyan
Write-Host "  Website: $websiteUrl" -ForegroundColor Cyan
Write-Host ""

if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw "Node.js/npm was not found. Install Node.js LTS, then run start.bat again."
}

if (-not (Test-Path $pythonExe)) {
    if (-not (Get-Command py.exe -ErrorAction SilentlyContinue) -and
        -not (Get-Command python.exe -ErrorAction SilentlyContinue)) {
        throw "Python 3 was not found. Install Python 3.11 or later, then run start.bat again."
    }

    Write-Host "Creating the backend Python environment..." -ForegroundColor Yellow
    if (Get-Command py.exe -ErrorAction SilentlyContinue) {
        & py.exe -3 -m venv $pythonExe.Replace("\Scripts\python.exe", "")
    } else {
        & python.exe -m venv $pythonExe.Replace("\Scripts\python.exe", "")
    }
    if ($LASTEXITCODE -ne 0) { throw "Could not create the backend Python environment." }

    Write-Host "Installing backend dependencies..." -ForegroundColor Yellow
    & $pythonExe -m pip install -r (Join-Path $backend "requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "Could not install backend dependencies." }
}

if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    Write-Host "Installing website dependencies..." -ForegroundColor Yellow
    Push-Location $frontend
    try {
        & npm.cmd install
        if ($LASTEXITCODE -ne 0) { throw "Could not install website dependencies." }
    } finally {
        Pop-Location
    }
}

if (-not (Test-BackendReady)) {
    if (Test-PortListening 8000) {
        throw "Port 8000 is occupied by a service that is not reporting a healthy database. Close that service and retry."
    }

    Write-Host "Starting API and database service..." -ForegroundColor Green
    $env:PYTHONIOENCODING = "utf-8"
    Start-Process -FilePath $pythonExe `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000") `
        -WorkingDirectory $backend

    $backendReady = $false
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        Start-Sleep -Milliseconds 500
        if (Test-BackendReady) { $backendReady = $true; break }
    }
    if (-not $backendReady) {
        throw "The API/database did not become ready. Check the backend terminal and backend\.env."
    }
} else {
    Write-Host "API and database are already healthy." -ForegroundColor Green
}

if (-not (Test-WebsiteReady)) {
    if (Test-PortListening 3000) {
        Write-Host "Waiting for the existing website to connect to the restarted API..." -ForegroundColor Yellow
        $websiteReady = $false
        for ($attempt = 0; $attempt -lt 20; $attempt++) {
            Start-Sleep -Milliseconds 500
            if (Test-WebsiteReady) { $websiteReady = $true; break }
        }
        if (-not $websiteReady) {
            throw "Port 3000 is occupied by a website that cannot reach the healthy API. Close that service and retry."
        }
    } else {
        Write-Host "Starting the website..." -ForegroundColor Green
        $frontendCommand = "Set-Location -LiteralPath '$frontend'; `$env:BACKEND_URL='$apiUrl'; npm.cmd run dev"
        Start-Process -FilePath "powershell.exe" `
            -ArgumentList @("-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $frontendCommand) `
            -WorkingDirectory $frontend

        $websiteReady = $false
        for ($attempt = 0; $attempt -lt 60; $attempt++) {
            Start-Sleep -Milliseconds 500
            if (Test-WebsiteReady) { $websiteReady = $true; break }
        }
        if (-not $websiteReady) {
            throw "The website did not become ready. Check the frontend terminal."
        }
    }
} else {
    Write-Host "Website and API proxy are already healthy." -ForegroundColor Green
}

Write-Host ""
Write-Host "  FINMIND AI is ready." -ForegroundColor Green
Write-Host "  Open:     $websiteUrl" -ForegroundColor Cyan
Write-Host "  API docs: $websiteUrl/api/docs" -ForegroundColor Cyan
Write-Host "  Health:   $websiteUrl/api/health (includes database readiness)" -ForegroundColor Cyan
Write-Host ""
Start-Process $websiteUrl
