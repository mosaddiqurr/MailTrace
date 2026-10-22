# Architecture

The React/TypeScript client uses the `/api/analyses` workflow and is served by Vite during development or FastAPI from `frontend/dist` in production. FastAPI validates input, invokes the bounded Python email parser, persists one evidence analysis inside an automatically created compatible case, and returns structured JSON. SQLAlchemy targets local SQLite; Alembic owns migrations. Original bytes are stored separately under generated identifiers.

The parser separates direct headers, receiver-reported authentication, derived alignment/hop data, heuristic observations, assessment, and limitations. Reports are generated from the same persisted result used by the UI.

The landing-page sculpture is independent of evidence processing. In supporting browsers an OffscreenCanvas worker receives only the canvas, dimensions, pixel ratio, and visibility state. It caches geometry and batches drawing; route cleanup terminates it. An optimized main-thread renderer is the fallback. Static hero and capability components skip rerendering during header entry, and all visual assets and fonts are self-hosted. See [interface design](UI_DESIGN.md) and [performance verification](PERFORMANCE.md).

## Local-first data flow

```mermaid
flowchart TB
    User[User]

    subgraph Local[Local machine — email evidence stays local by default]
        UI[React + TypeScript frontend]
        Visual[Decorative canvas worker<br/>no email evidence]
        API[FastAPI API]
        Services[Email parsing and forensic analysis services]
        ORM[SQLAlchemy]
        DB[(SQLite local database)]
        Migrations[Alembic migrations]
        Evidence[(Local filesystem<br/>retained original evidence)]
        Reports[Report and export generation]

        UI -->|.eml upload or pasted headers| API
        UI -. canvas and visibility only .-> Visual
        API --> Services
        Services --> ORM
        ORM --> DB
        Migrations -. schema migrations .-> DB
        Services -->|optional retained originals| Evidence
        API --> Reports
        ORM --> Reports
        Evidence -->|when included in a bundle| Reports
        Reports -->|PDF, JSON, CSV, text, HTML, ZIP| UI
    end

    User --> UI
    Services -. only when explicitly enabled .-> DNS[Current DNS enrichment]
```

The dotted DNS path is the only analysis-related network path and is disabled by default. It provides current context, not historical DNS reconstruction or fresh authentication verification. SQLite records and retained originals default to the Git-ignored `data/` directory. Exports are generated on demand from the persisted analysis and, for bundles, any retained original evidence.
