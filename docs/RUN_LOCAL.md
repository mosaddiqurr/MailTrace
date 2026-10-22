# Run locally

Use Python 3.12+ and Node.js 24+. The PowerShell launcher creates an isolated `.venv` when missing, installs Python dependencies on that first run, applies Alembic migrations, builds a missing frontend, and serves the local application.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-local.ps1
```

Open `http://127.0.0.1:8000`. Keep the terminal open and press Ctrl+C to stop.

## Frontend development

```powershell
npm.cmd ci --prefix frontend
powershell -ExecutionPolicy Bypass -File .\scripts\run-local.ps1 -Development
```

Open `http://127.0.0.1:5173`. Vite proxies `/api` to the coordinated backend on port 8000. The hero's worker is built and served by Vite along with the application.

## Update an existing checkout

The launcher reuses an existing `frontend/dist` build. After pulling new source, explicitly refresh dependencies and rebuild so the browser receives the new UI:

```powershell
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
npm.cmd ci --prefix frontend
npm.cmd run build --prefix frontend
powershell -ExecutionPolicy Bypass -File .\scripts\run-local.ps1
```

## Manual setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
npm.cmd ci --prefix frontend
npm.cmd run build --prefix frontend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn mailtrace.main:app --host 127.0.0.1 --port 8000
```

The same Python, Alembic, npm, and Uvicorn commands work on other platforms using that platform's virtual-environment Python path. Docker configuration is also included in the repository.

## Data and browser checks

Runtime data defaults to the Git-ignored `data/` directory. Configure paths and bounds with `MAILTRACE_` environment variables; see [config.py](../mailtrace/config.py). Current-DNS enrichment is off by default. Do not commit local evidence or databases.

Before the first Playwright or screenshot run, use `npx playwright install chromium` from `frontend/`. Browser tests and screenshot capture require port 8000 to be free and use their own isolated temporary evidence directory. See [testing](TESTING.md).
