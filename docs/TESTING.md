# Testing

The complete PowerShell gate is `powershell -ExecutionPolicy Bypass -File .\scripts\validate.ps1`. Install Python dev dependencies and the locked frontend dependencies first. Before the first browser run, execute `npx playwright install chromium` in `frontend/`.

## Individual checks

```powershell
.\.venv\Scripts\python.exe -m ruff check mailtrace tests alembic scripts
.\.venv\Scripts\python.exe -m ruff format --check mailtrace tests alembic scripts
.\.venv\Scripts\python.exe -m mypy mailtrace tests
.\.venv\Scripts\python.exe -m pytest --cov=mailtrace --cov-branch
npm.cmd run lint --prefix frontend
npm.cmd run test --prefix frontend
npm.cmd run build --prefix frontend
npm.cmd run test:e2e --prefix frontend
npm.cmd audit --prefix frontend --audit-level=high
```

Backend tests cover bounded parsing, reported authentication, alignment, ARC, delivery, MIME, attachments, observations, persistence, retention, reports, APIs, DNS guards, malformed inputs, and safe exports. Frontend tests cover intake, reports, missing evidence, history, settings, errors, keyboard interaction, and drag/drop.

The animation tests check finite geometry, drawing batches, frame budgeting, visibility, cleanup, and one-time OffscreenCanvas transfer across a StrictMode effect replay. Playwright exercises the worker and canvas fallback, continuous motion with both motion preferences, off-screen suspension/resume, worker disposal on navigation, desktop/mobile fit, and accessibility across routes.

The recorded interface candidate passed 19 unit tests at 98.68% line coverage and 23 browser checks, with one intentional desktop skip for a mobile-only case. Dated results live in [validation](VALIDATION.md) and [performance](PERFORMANCE.md); new runs and CI are authoritative for later changes.

## Isolated real-browser data

Build the frontend before browser tests and stop any application listening on port 8000. Global setup refuses to reuse an existing listener, starts a temporary Uvicorn process with a unique `MAILTRACE_DATA_DIR`, waits for health, then closes the process and removes test data. On Windows, cleanup stops the owned launcher's process tree so its interpreter cannot remain listening; listener checks distinguish a live server from closed sockets in TIME_WAIT. Your ordinary local evidence is not used.

Browser traces are retained on failure under the ignored `frontend/test-results/` directory. Visual review captures are written under the ignored `.tmp/ui-review/` directory. `npm run docs:screenshots --prefix frontend` separately regenerates the tracked documentation images using the same isolation; see [the screenshot guide](screenshots/README.md).

## GitHub Actions

The validation workflow runs Ruff, formatting, strict MyPy, and pytest on Linux and Windows. Its Linux frontend job installs locked packages, checks lint and coverage, builds the app, audits dependencies, installs Chromium and the backend, then runs the desktop/mobile Playwright suite. Failed browser traces are uploaded with a seven-day retention period.

Automatic accessibility checks do not replace keyboard, focus, contrast, reading-order, and assistive-technology review. Lighthouse scores and short input-response profiles are controlled local samples rather than field performance guarantees.
