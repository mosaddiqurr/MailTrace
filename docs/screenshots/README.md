# Application screenshots

These captures show the current MailTrace UI at **1440 × 900**, device scale factor 1, with synthetic email evidence only. They are referenced by the repository README.

## Regenerate

Install the locked frontend dependencies and Chromium, build the application, and free port 8000:

```powershell
npm.cmd ci --prefix frontend
npm.cmd run build --prefix frontend
Set-Location frontend
npx.cmd playwright install chromium
npm.cmd run docs:screenshots
```

The capture script owns a temporary Uvicorn server and a new isolated data directory. It never reads the normal local analysis history. It waits for fonts and the hero drawing, uses only packaged fixtures, saves the PNGs below, then closes the browser and removes its temporary data. Node.js 24+ is required. Reduced-motion styling makes capture deterministic outside the continuously animated hero.

| File | View | Evidence |
| --- | --- | --- |
| [00-landing.png](00-landing.png) | Animated email hero and start of the workspace | None |
| [01-analysis-input.png](01-analysis-input.png) | Compact upload/pasted-header workspace | None |
| [02-investigation-overview.png](02-investigation-overview.png) | Assessment, summary, and report navigation | `spf-fail-reply-to.eml` |
| [03-authentication-analysis.png](03-authentication-analysis.png) | Reported authentication and verification disclaimer | `spf-fail-reply-to.eml` |
| [04-delivery-path.png](04-delivery-path.png) | Ordered delivery evidence and trust-boundary note | `spf-fail-reply-to.eml` |
| [05-urls-attachments.png](05-urls-attachments.png) | Static attachment inventory and hash | `double-extension.eml` |
| [06-report-or-history.png](06-report-or-history.png) | Searchable local history | Three synthetic fixtures |

Keep filenames stable. Do not add real email content, private addresses, personal history, or user evidence to documentation images. The [original logo source](../branding/mailtrace-logo.png) is retained separately from the optimized public UI assets.
