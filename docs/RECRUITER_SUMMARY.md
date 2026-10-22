# Recruiter summary

MailTrace is a local-first email forensics application that reconstructs delivery paths, interprets reported authentication, compares identities, inventories content, and generates explainable reports without executing attachments or loading remote resources.

The project combines Python/FastAPI, SQLAlchemy/SQLite, Alembic, React/TypeScript, responsive design, export safety, and automated backend and browser testing. Its procedural email hero runs in an OffscreenCanvas worker where supported, with lifecycle cleanup and a tested fallback. The [performance report](PERFORMANCE.md) records clean Lighthouse scores and input-response improvements under CPU slowdown. Current UI captures and setup instructions are in the [main README](../README.md).
