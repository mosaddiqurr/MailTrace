# Documentation

MailTrace's documentation is grouped by the question a reviewer or operator is trying to answer.

## Understand the project

- [Architecture](ARCHITECTURE.md) — components, local data flow, persistence, exports, and optional DNS.
- [Analysis methodology](ANALYSIS_METHODOLOGY.md) — separation of facts, reported claims, derived comparisons, observations, and assessments.
- [Email authentication](EMAIL_AUTHENTICATION.md) — SPF, DKIM, DMARC, ARC, identity alignment, and trust boundaries.
- [Portfolio case study](PORTFOLIO_CASE_STUDY.md) — problem, engineering approach, and demonstrated skills.
- [Recruiter summary](RECRUITER_SUMMARY.md) — concise project overview.

## Run and evaluate MailTrace

- [Run locally](RUN_LOCAL.md) — production-style and development startup.
- [Demo guide](DEMO_GUIDE.md) — privacy-safe walkthrough using synthetic fixtures.
- [Testing](TESTING.md) — backend, frontend, and real-browser coverage.
- [Recorded validation](VALIDATION.md) — v1.0.0 validation environment and results.
- [v1.0.0 release notes](RELEASE_NOTES_v1.0.0.md) — concise release summary and known limitations.
- [Screenshot capture checklist](screenshots/README.md) — required portfolio images and safe capture guidance.

## Security and evidence handling

- [Security](SECURITY.md) — bounded parsing and content-safety controls.
- [Privacy](PRIVACY.md) — local processing and the optional network boundary.
- [Data retention](DATA_RETENTION.md) — retained originals, deletion, and expiry behavior.
- [Exports](EXPORTS.md) — report formats and evidence-safety properties.
- [Limitations](LIMITATIONS.md) — claims MailTrace intentionally does not make.

Additional project records remain at the repository root: [`DECISIONS.md`](../DECISIONS.md), [`REQUIREMENTS_AUDIT.md`](../REQUIREMENTS_AUDIT.md), and [`KNOWN_ISSUES.md`](../KNOWN_ISSUES.md).
