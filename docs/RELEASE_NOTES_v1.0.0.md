# MailTrace v1.0.0

MailTrace v1.0.0 provides a local-first workflow for evidence-led email forensic triage.

## Highlights

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
- Docker configuration is included, but Docker runtime validation remains pending on the recorded validation host.
