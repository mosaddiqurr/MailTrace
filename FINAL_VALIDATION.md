# MailTrace Final Validation

Validation date: 20 August 2026

Host: Windows, Python 3.12.10, Node.js 24.15.0

## Release decision

The source candidate is ready for its first public GitHub commit. No commit, tag, or push was performed during validation.

## Remediation verification

- `Received` parsing now derives `from_ip` only from the actual `from` clause. Five exact regression cases cover by-only hosts, a Gmail-style IPv6 identifier, hostname/parenthesized IPv4, hostname/IPv4, and hostname/IPv6. All pass.
- Analysis list/detail serialization now uses an explicit `Evidence`/`Case` join. A stale-relationship regression reproduces the previous delete/list failure condition and passes without a 500 or deleted-record exposure.
- The SPA fallback test creates a controlled temporary static tree. Backend tests therefore pass in a source-only checkout before `frontend/dist` exists.
- Playwright owns a direct Python/Uvicorn child, bounds readiness globally and per request, and performs handle-based teardown. The full suite exited normally and an intentional no-tests failure also cleaned up. Port 8000 was free and no E2E temporary directory remained after both paths.
- A non-editable wheel installation placed all 24 `.eml` fixtures and required JSON catalogs in `site-packages`. The installed application returned 10 demos and loaded `aligned-business` with HTTP 201.
- The free-mail fixture uses the reserved synthetic address `accounts-helpdesk@freemail.example`; the scenario and expected `DOM-005` observation remain intact.
- Source references identify `frontend/public/logo.png` as the live asset. The two byte-identical, unused root `public/` duplicates were removed.

## Clean-source acceptance

A new 101-file source-only copy was created without Git metadata, environments, dependencies, builds, databases, `.env`, private `data/`, output, caches, coverage, browser artifacts, logs, or temporary directories.

From that copy:

- Python dependencies installed from a built, non-editable wheel.
- Locked frontend dependencies installed with `npm ci` (279 packages).
- Ruff: pass.
- Ruff format check: pass (23 files formatted).
- strict MyPy: pass (18 source files).
- pytest: 62 passed, one third-party Starlette/httpx deprecation warning.
- Backend branch coverage: 93.58% overall; parser 95%; reports 96%.
- Vitest: 13 passed across 2 files.
- Frontend coverage: 94.91% statements, 81.36% branches, 95.38% functions, 98.93% lines.
- ESLint: pass.
- TypeScript (`tsc --noEmit`): pass.
- Vite production build: pass.
- Playwright: 13 passed, 1 expected desktop skip.
- Playwright success and failure teardown: pass; port 8000 released.
- Alembic fresh database migration: `0002_analysis_results (head)`.
- Installed-package demo API: 10 demos; demo load HTTP 201.
- npm audit: 0 vulnerabilities.
- `pip check`: no broken requirements.
- `pip-audit`: no known vulnerabilities; the local `mailtrace` project itself is correctly reported as not present on PyPI.

The real-stack Playwright run exercised health, static assets, pasted-header analysis, `.eml` upload, analysis retrieval, history persistence/deletion, settings persistence, validation, desktop/mobile layouts, and accessibility checks.

## Repository and privacy review

- `data/` remains ignored and untouched. It contains retained local evidence and must never be committed.
- The known CSA evidence path is ignored by `.gitignore`.
- No candidate file hash matches a retained evidence file.
- No candidate file contains a consumer-provider email address, secret marker, credential pattern, private-key marker, or absolute personal workspace path.
- All 82 distinct candidate email addresses use reserved/example-style domains.
- No database, runtime data, output, environment, dependency directory, build, coverage file, cache, log, or browser artifact appears in the Git candidate.
- Candidate size is approximately 1 MiB. The only files above 100 KiB are the intentional logo asset and `frontend/package-lock.json`.
- `git diff --check` and staged whitespace checks report no errors. The repository has no HEAD commit yet and the intended source is currently untracked.

## Docker status

`Dockerfile` and `compose.yaml` are present. Docker runtime was not validated on this host because the Docker command is unavailable. No Docker execution claim is made.

## Known limitations

- Authentication results are receiver-reported evidence, not fresh cryptographic verification.
- Headers can be forged before a trusted receiving boundary.
- Current DNS cannot reproduce historical authentication state; optional DNS enrichment is disabled by default.
- Attachments are inspected statically, not executed or malware-scanned.
- URLs are extracted but not fetched or reputation-checked.
- One deprecation warning originates from FastAPI's current TestClient compatibility layer and does not fail validation.
