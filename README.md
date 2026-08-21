# MailTrace

MailTrace is a local-first email forensic triage application for turning raw `.eml` files or pasted headers into an evidence-led investigation report. It helps analysts and learners interpret delivery paths, sender identity differences, and authentication results without sending message data to an external service.

## Capabilities

- Parses bounded RFC email headers and MIME structures without rendering active HTML or executing attachments.
- Reconstructs `Received` hops, timestamps, and IP classifications.
- Extracts reported SPF, DKIM, DMARC, and ARC evidence and explains identity alignment.
- Inventories attachments and URLs, including hashes and display-versus-destination differences.
- Stores analyses locally and exports PDF, JSON, CSV, plain text, HTML, and ZIP bundles.
- Provides responsive React workflows for upload, pasted headers, history, settings, and deletion.

MailTrace distinguishes facts, reported authentication claims, derived comparisons, and contextual observations. Authentication headers describe what a receiving system reported; MailTrace does not freshly verify DKIM signatures, reproduce historical DNS, or prove that a message is safe or malicious.

## Architecture

The frontend uses React, TypeScript, Vite, and TanStack Query. FastAPI provides the API and production static hosting, with SQLAlchemy and SQLite for local persistence and Alembic for migrations. Pytest, Vitest, ESLint, MyPy, Ruff, and Playwright cover the backend, frontend, and real browser workflow.

## Run from a fresh clone

Requirements: Python 3.12+, Node.js 24+, npm, and Windows PowerShell.

For the production-style local application:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-local.ps1
```

The script creates `.venv` when missing, installs Python dependencies, applies Alembic migrations, builds the frontend when needed, and serves MailTrace at `http://127.0.0.1:8000`. Keep that terminal open; press Ctrl+C to stop.

For frontend development with hot reload:

```powershell
Set-Location .\frontend
npm.cmd ci
Set-Location ..
powershell -ExecutionPolicy Bypass -File .\scripts\run-local.ps1 -Development
```

Open `http://127.0.0.1:5173`. Vite proxies `/api` to the FastAPI server on port 8000.

To install or migrate manually:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Set-Location .\frontend
npm.cmd ci
npm.cmd run build
Set-Location ..
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Runtime data defaults to `data/`. It is intentionally Git-ignored because it can contain private evidence. Configuration uses `MAILTRACE_` environment variables; see `mailtrace/config.py` for available limits and paths.

## Demo data

Synthetic examples are packaged under `mailtrace/fixtures/`. Start with `aligned-business.eml` for a low-concern message and `spf-fail-reply-to.eml` for reported authentication failure and sender-identity differences. The application also exposes these through its demo API. No real email evidence belongs in fixtures.

## Validation

Run the complete local validation sequence:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate.ps1
```

Useful individual commands:

```powershell
.\.venv\Scripts\python.exe -m ruff check mailtrace tests alembic scripts
.\.venv\Scripts\python.exe -m mypy mailtrace tests
.\.venv\Scripts\python.exe -m pytest --cov=mailtrace --cov-branch
Set-Location .\frontend
npm.cmd run lint
npm.cmd run test
npm.cmd run build
npm.cmd run test:e2e
npm.cmd audit --audit-level=high
```

`npm run test:e2e` owns its temporary Uvicorn process, waits for readiness, and releases port 8000 after the run.

## Security, privacy, and limitations

Message processing is local by default. MailTrace does not load remote images, follow links, execute attachments, or render active message HTML. Input sizes, header counts, MIME depth, part counts, attachment counts, decoded bytes, URL counts, and processing time are bounded. Optional current-DNS enrichment is disabled until the user enables it; enabling it makes network DNS requests.

Header evidence can be forged before a trusted receiving boundary. Current DNS cannot reconstruct historical authentication state. Static attachment inspection is not malware analysis, and URL extraction is not reputation checking. See `docs/` for the detailed methodology, architecture, security model, privacy notes, retention behavior, and limitations.

Docker configuration is included in `Dockerfile` and `compose.yaml`, but Docker runtime was not validated on the current host because Docker was unavailable.
