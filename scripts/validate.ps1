$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$PytestBaseTemp = Join-Path $ProjectRoot ".tmp\pytest-validation-$([guid]::NewGuid())"

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

Invoke-Checked { & $Python -m ruff check mailtrace tests alembic scripts } "Ruff"
Invoke-Checked { & $Python -m ruff format --check mailtrace tests alembic scripts } "format check"
Invoke-Checked { & $Python -m mypy mailtrace tests } "MyPy"
Invoke-Checked {
    & $Python -m pytest -p no:cacheprovider --basetemp $PytestBaseTemp --cov=mailtrace --cov-branch
} "backend tests"
Push-Location frontend
Invoke-Checked { npm.cmd run lint } "frontend lint"
Invoke-Checked { npm.cmd run test } "frontend tests"
Invoke-Checked { npm.cmd run build } "frontend build"
Invoke-Checked { npm.cmd audit --audit-level=high } "npm audit"
Invoke-Checked { npm.cmd run test:e2e } "Playwright"
Pop-Location
Write-Host "MailTrace validation completed successfully."
