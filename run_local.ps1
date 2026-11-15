# Run the whole GigBid system on this laptop (viva / demo): GigSim, the three MCP servers, the API
# and the web app. First run sets up a local Python environment (.venv-local) and web dependencies.
#
#   powershell -ExecutionPolicy Bypass -File .\run_local.ps1
#
# Then open http://localhost:3000 and sign in as reviewer@gigbid.dev (password: REVIEWER_PASSWORD in .env).
# Ctrl+C stops everything.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$venv = ".venv-local"

if (-not (Test-Path ".env")) { throw ".env is missing (it holds the database URL and API keys)." }

if (-not (Test-Path "$venv\Scripts\python.exe")) {
    Write-Host "First run: creating $venv with Python 3.12 (a few minutes)..."
    python -m pip install --user --quiet --disable-pip-version-check uv
    python -m uv venv $venv --python 3.12
}
$env:UV_PROJECT_ENVIRONMENT = $venv
Write-Host "Installing Python dependencies (fast after the first run)..."
python -m uv sync --frozen --extra dev --quiet

if (-not (Test-Path "apps\web\node_modules")) {
    Write-Host "Installing web dependencies..."
    npm --prefix apps/web ci --no-audit --no-fund
}

$env:GIGSIM_SEED_DIR = "data/deploy_seed"
$env:GIGSIM_DB = "data/cache/gigsim_local.sqlite"
$env:GIGSIM_LLM_DISABLED = "1"
$env:GIGSIM_ERROR_RATE = "0"
$env:GIGSIM_CLOCK_SPEED = "10"
$env:WORKER_MODE = "inline"
$env:MODEL_PROFILE = "paid"
$env:APP_ENV = "development"
$env:PUBLIC_BASE_URL = "http://localhost:3000"
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"

Write-Host ""
Write-Host "Starting GigSim, MCP servers, API and web app. Logs: data\cache\logs\"
Write-Host "When 'web' is ready, open http://localhost:3000"
& "$venv\Scripts\python.exe" scripts/dev.py --web
