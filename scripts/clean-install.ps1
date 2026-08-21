$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
$PytestBaseTemp = Join-Path $ProjectRoot ".tmp\pytest-clean-install-$([guid]::NewGuid())"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command,
        [Parameter(Mandatory = $true)]
        [string]$Label
    )
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE."
    }
}

$CleanPython = Join-Path $ProjectRoot ".clean-venv\Scripts\python.exe"
if (-not (Test-Path $CleanPython)) { python -m venv .clean-venv }
Invoke-Checked { & $CleanPython -m pip install --upgrade pip } "pip upgrade"
Invoke-Checked { & $CleanPython -m pip install -e ".[dev]" } "Python dependency installation"
Push-Location frontend
Invoke-Checked { npm.cmd ci } "npm clean installation"
Invoke-Checked { npm.cmd run build } "frontend production build"
Pop-Location
$env:MAILTRACE_DATA_DIR = Join-Path $ProjectRoot ".test-tmp\clean-install-data"
Invoke-Checked { & $CleanPython -m alembic upgrade head } "database migration"
Invoke-Checked { & $CleanPython -m pytest -p no:cacheprovider --basetemp $PytestBaseTemp } "backend tests"
Write-Host "Clean isolated installation passed."
