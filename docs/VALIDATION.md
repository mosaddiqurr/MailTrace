# Validation records

## Interface and performance update — 22 October 2026

The redesigned interface passed the production build, ESLint, 19 Vitest tests (98.68% line coverage), and 23 desktop/mobile Playwright checks. One desktop instance of a mobile-only test is intentionally skipped. The browser run verifies the visual worker, fallback, visibility, cleanup, evidence workflow, exports, navigation, and route accessibility.

The final clean desktop Lighthouse run scored 100 in Performance, Accessibility, Best Practices, and SEO, with 0.6 s LCP, 0 ms Total Blocking Time, and zero layout shift. A separate 4× CPU slowdown input sample improved from 544 ms to 64 ms at the 95th percentile. See [the performance report](PERFORMANCE.md) for configuration and measurement limits.

The repository refresh replaces the old UI screenshots, documents reproducible synthetic-only capture, keeps the original logo outside public build assets, excludes local working notes, and adds the browser suite to CI. The following v1.0.0 record is historical; current CI is authoritative for later commits.

The repository publication checks also passed Ruff, formatting, strict MyPy, and 62 backend tests at 93.63% branch-aware coverage. Vite and Vitest were updated to compatible security-patched versions; the npm dependency audit reports zero vulnerabilities. The existing third-party TestClient deprecation warning remains documented in [known issues](../KNOWN_ISSUES.md).

## v1.0.0 source candidate

Validation date: 20 August 2026

Host: Windows, Python 3.12.10, Node.js 24.15.0

### Release decision

The v1.0.0 source candidate passed the recorded clean-source acceptance suite. This report captures the validation evidence from that candidate; current CI remains the authoritative check for later commits.

### Remediation verification

- `Received` parsing derives `from_ip` only from the actual `from` clause. Five exact regression cases cover by-only hosts, a Gmail-style IPv6 identifier, hostname/parenthesized IPv4, hostname/IPv4, and hostname/IPv6. All passed.
- Analysis list/detail serialization uses an explicit `Evidence`/`Case` join. A stale-relationship regression reproduces the previous delete/list failure condition and passed without a 500 response or deleted-record exposure.
- The SPA fallback test creates a controlled temporary static tree. Backend tests therefore pass in a source-only checkout before `frontend/dist` exists.
- Playwright owns a direct Python/Uvicorn child, bounds readiness globally and per request, and performs handle-based teardown. The full suite exited normally and an intentional no-tests failure also cleaned up. Port 8000 was free and no E2E temporary directory remained after both paths.
- A non-editable wheel installation placed all 24 `.eml` fixtures and required JSON catalogs in `site-packages`. The installed application returned 10 demos and loaded `aligned-business` with HTTP 201.
- The free-mail fixture uses the reserved synthetic address `accounts-helpdesk@freemail.example`; the scenario and expected `DOM-005` observation remain intact.
- Source references identify `frontend/public/logo.png` as the live asset. The two byte-identical, unused root `public/` duplicates were removed.

### Clean-source acceptance

A clean source-only copy was created without Git metadata, environments, dependencies, builds, databases, `.env`, private `data/`, output, caches, coverage, browser artifacts, logs, or temporary directories.

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
- `pip-audit`: no known vulnerabilities; the local `mailtrace` project itself was correctly reported as not present on PyPI.

The real-stack Playwright run exercised health, static assets, pasted-header analysis, `.eml` upload, analysis retrieval, history persistence/deletion, settings persistence, validation, desktop/mobile layouts, and accessibility checks.

### Repository and privacy review

- `data/` remained ignored and untouched. It contains retained local evidence and must never be committed.
- The known CSA evidence path was ignored by `.gitignore`.
- No candidate file hash matched a retained evidence file.
- No candidate file contained a consumer-provider email address, secret marker, credential pattern, private-key marker, or absolute personal workspace path.
- All 82 distinct candidate email addresses used reserved/example-style domains.
- No database, runtime data, output, environment, dependency directory, build, coverage file, cache, log, or browser artifact appeared in the Git candidate.
- Candidate size was approximately 1 MiB. The only files above 100 KiB were the intentional logo asset and `frontend/package-lock.json`.
- `git diff --check` and staged whitespace checks reported no errors.

### Docker status

`Dockerfile` and `compose.yaml` are present. Docker runtime was not validated on this host because the Docker command was unavailable. No Docker execution claim is made.

### Known limitations

- Authentication results are receiver-reported evidence, not fresh cryptographic verification.
- Headers can be forged before a trusted receiving boundary.
- Current DNS cannot reproduce historical authentication state; optional DNS enrichment is disabled by default.
- Attachments are inspected statically, not executed or malware-scanned.
- URLs are extracted but not fetched or reputation-checked.
- One deprecation warning originated from FastAPI's TestClient compatibility layer and did not fail validation.
