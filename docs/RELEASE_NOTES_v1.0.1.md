# MailTrace v1.0.1

MailTrace v1.0.1 is a repository presentation and documentation patch release built on the validated local-first email forensic triage functionality introduced in v1.0.0. It does not expand MailTrace's forensic claim boundaries.

## Repository improvements

- Polished the README opening for a concise, recruiter-friendly project overview.
- Added six real application screenshots captured with synthetic email evidence.
- Added a Mermaid architecture diagram covering the local data flow, persistence, evidence storage, report generation, migrations, and optional DNS enrichment.
- Added the MIT License.
- Added CI, Python, and license status badges based on the repository's actual configuration.
- Organized detailed technical, security, privacy, validation, and testing documentation under a clearer documentation index.

## Existing validated functionality

- Analyze `.eml` files and pasted email headers locally.
- Reconstruct delivery paths from ordered `Received` evidence.
- Interpret receiver-reported SPF, DKIM, DMARC, and ARC results.
- Compare sender identities and authentication alignment.
- Inspect MIME structure, attachment metadata and hashes, and extracted URLs.
- Retain and delete analysis history on the local device.
- Export reports as PDF, JSON, CSV, text, HTML, and ZIP bundles.
- Validate the backend, frontend, and real-browser workflow with automated tests.

## Known limitations

- Authentication headers are receiver-reported evidence, not fresh cryptographic verification.
- MailTrace does not reconstruct historical DNS state.
- Attachments are inspected statically and are not dynamically malware-analyzed.
- Extracted URLs are not automatically fetched or reputation-checked.
- No assessment definitively classifies a message as malicious or benign.
- Docker configuration is included, but Docker runtime validation remains pending on the recorded validation host.
