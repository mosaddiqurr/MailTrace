# Screenshot Capture Checklist

The README screenshot references are staged but intentionally disabled until real captures are supplied. Use only MailTrace's synthetic fixtures; never capture private or real email evidence.

## Capture settings

- Use a consistent desktop viewport of **1440 × 900** at 100% browser zoom.
- Run the production-style local application at `http://127.0.0.1:8000`.
- Prefer `spf-fail-reply-to.eml` for authentication and sender-alignment evidence.
- Prefer `html-link-mismatch.eml` or `mime-extension-mismatch.eml` for URL and attachment evidence.
- Keep the MailTrace navigation and page title visible; crop browser chrome consistently.
- Check that filenames, addresses, message IDs, IPs, and report content all come from the packaged synthetic fixtures.
- Save PNG files at their native capture size without decorative frames or annotations.

## Required files

1. `01-analysis-input.png` — New Analysis page with both `.eml` upload and pasted-header input methods visible before submission.
2. `02-investigation-overview.png` — Completed synthetic analysis showing the subject, evidence summary, assessment, confidence, and strongest observations.
3. `03-authentication-analysis.png` — Authentication section showing reported SPF, DKIM, DMARC, or ARC evidence alongside identity-alignment context.
4. `04-delivery-path.png` — Delivery section showing ordered `Received` hops, timestamps, hosts, and IP classifications.
5. `05-urls-attachments.png` — MIME, URL, and attachment sections showing hashes or display-versus-destination evidence.
6. `06-report-or-history.png` — Either the export controls on a completed report or History with multiple synthetic analyses and deletion controls.

Place all six files in this directory. Then uncomment the matching Markdown image line above each caption in the repository README and verify the images render on GitHub.
