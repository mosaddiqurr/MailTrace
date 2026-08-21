param([switch]$Development)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    python -m venv .venv
    & $Python -m pip install --upgrade pip
    & $Python -m pip install -e ".[dev]"
}
& $Python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw "Database migration failed." }
if (-not $Development) {
    if (-not (Test-Path "frontend\dist\index.html")) {
        Push-Location frontend
        npm.cmd ci
        npm.cmd run build
        Pop-Location
    }
    Write-Host "MailTrace is available at http://127.0.0.1:8000"
    & $Python -m uvicorn mailtrace.main:app --host 127.0.0.1 --port 8000
    exit $LASTEXITCODE
}
$Backend = Start-Process -FilePath $Python -ArgumentList @(
    "-m", "uvicorn", "mailtrace.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload"
) -WorkingDirectory $ProjectRoot -WindowStyle Hidden -PassThru
try {
    Write-Host "MailTrace development UI is available at http://127.0.0.1:5173"
    Push-Location frontend
    npm.cmd run dev
    Pop-Location
} finally {
    if (-not $Backend.HasExited) { Stop-Process -Id $Backend.Id }
}
