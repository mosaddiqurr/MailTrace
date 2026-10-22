# Demo guide

1. Start MailTrace and use **Start an investigation** to reach the evidence workspace.
2. Upload [`aligned-business.eml`](../mailtrace/fixtures/aligned-business.eml). Select **Analyse email** and review the assessment, identity, and reported authentication. A low-concern result is not a safety guarantee.
3. Start another investigation with [`spf-fail-reply-to.eml`](../mailtrace/fixtures/spf-fail-reply-to.eml). Inspect the authentication notice, sender differences, ordered delivery path, and raw evidence.
4. Upload [`double-extension.eml`](../mailtrace/fixtures/double-extension.eml) to inspect attachment metadata and SHA-256 evidence. The attachment is never executed.
5. Use **Export report** for JSON or PDF, then visit **History** to search and reopen the synthetic investigations. Deletion removes retained local report data and evidence.
6. Visit **Methodology** for interpretation limits and **Settings** for retention and optional current-DNS enrichment. DNS remains disabled unless explicitly enabled.

The landing sculpture is decorative and runs independently of evidence processing. The UI has no sample-email card; use the packaged fixtures for demonstrations. Never include real private evidence in screenshots or the repository.
