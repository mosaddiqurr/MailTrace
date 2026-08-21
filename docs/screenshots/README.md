# Application Screenshots

These README screenshots were captured from MailTrace using synthetic email evidence. Never replace them with captures containing private or real email evidence.

## Replacement guidance

- Use a consistent desktop viewport of **1440 × 900** at 100% browser zoom.
- Run the production-style local application at `http://127.0.0.1:8000`.
- Prefer `spf-fail-reply-to.eml` for authentication and sender-alignment evidence.
- Prefer `html-link-mismatch.eml` or `mime-extension-mismatch.eml` for URL and attachment evidence.
- Keep the MailTrace navigation and page title visible; crop browser chrome consistently.
- Check that filenames, addresses, message IDs, IPs, and report content all come from the packaged synthetic fixtures.
- Save PNG files at their native capture size without decorative frames or annotations.

## README files

1. `01-analysis-input.png` — New Analysis page with both `.eml` upload and pasted-header input methods visible before submission.
2. `02-investigation-overview.png` — Completed synthetic analysis showing the subject, evidence summary, assessment, confidence, and strongest observations.
3. `03-authentication-analysis.png` — Authentication section showing reported SPF, DKIM, and DMARC evidence with the verification disclaimer and expandable alignment and ARC context.
4. `04-delivery-path.png` — Delivery section showing one ordered `Received` hop, its timestamp, and access to the raw evidence.
5. `05-urls-attachments.png` — MIME summary, non-rendered plain-text preview, and attachment metadata with SHA-256 evidence.
6. `06-report-or-history.png` — Local History with multiple synthetic analyses, assessment summaries, search, and deletion controls.

All six files are referenced from the repository README with paths relative to the repository root. Keep these filenames stable so GitHub continues to render the walkthrough correctly.
