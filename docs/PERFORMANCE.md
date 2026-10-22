# MailTrace performance verification

The landing-page animation runs in an OffscreenCanvas worker in supporting browsers. The page handles only viewport, visibility, and lifecycle messages. Older browsers use the same optimized renderer on the page. There is no motion control: the sculpture keeps moving while visible, suspends outside the viewport or in a hidden document, and resumes automatically. Leaving the landing page terminates the worker.

The renderer caches geometry and projection inputs, batches the particle field into sixteen paint operations, avoids per-frame layout reads and canvas shadow blurs, caps backing resolution and frame rate, and uses less subpixel detail on phones. Static hero and capability sections skip React rerenders during header entry. The original 572,403-byte PNG is replaced in the UI by lossless 6,870-byte and 19,178-byte WebP variants; platform icons are also right-sized. The primary font is preloaded, and hero text has no delayed entrance.

## Controlled desktop audit

Measured on 22 October 2026 with Lighthouse 13.5.0, the production Vite build served by local Uvicorn, Chromium without extensions, and `--preset=desktop`. Before and after use the same settings.

| Metric | Before | After |
| --- | ---: | ---: |
| Performance | 92 | 100 |
| Accessibility | 100 | 100 |
| Best Practices | 100 | 100 |
| SEO | 100 | 100 |
| First Contentful Paint | 0.6 s | 0.5 s |
| Largest Contentful Paint | 1.5 s | 0.6 s |
| Total Blocking Time | 130 ms | 0 ms |
| Speed Index | 1.0 s | 0.7 s |
| Cumulative Layout Shift | 0 | 0 |

Raw audit and interaction reports are local review artifacts under the Git-ignored `.tmp/ui-review/` directory. Scores vary with hardware, browser extensions, throttling, and background load. Browser-extension scripts are outside the application bundle.

## Interaction profile

Headless Chromium, 390 × 844 viewport, device pixel ratio 2, 4× CPU slowdown, the same synthetic header-entry script before and after. Both the sculpture and worker were verified active in the final run. These event measurements are a short local sample, not field INP.

| During header entry | Before | After |
| --- | ---: | ---: |
| Event duration, 95th percentile | 544 ms | 64 ms |
| Input delay, 95th percentile | 263 ms | 6.8 ms |
| Main-thread long tasks | 34 | 0 |
| Typing timed out | Yes | No |

The final visible-hero sample also recorded zero main-thread long tasks on desktop and under mobile CPU slowdown. Page-thread draw counters are zero because drawing moved into the worker; this does not mean animation stopped and is not a worker FPS measurement.

## Regression checks

- Production build and ESLint pass.
- 19 unit tests pass, with 98.68% line coverage. These include finite animation geometry, batched drawing, frame budgeting, visibility, cleanup, and one-time canvas transfer across a StrictMode replay.
- 23 desktop/mobile browser checks pass; one desktop instance of a mobile-only check is intentionally skipped. Coverage includes continuous motion under both motion preferences, worker and fallback rendering, off-screen suspension/resume, worker disposal on navigation, uploads, analysis, history, settings, exports, accessibility, and viewport fit.
- Review images include `.tmp/ui-review/desktop-home.png` and `mobile-home.png`.

Rebuild with `npm run build --prefix frontend`. Run `npm run lint --prefix frontend`, `npm run test --prefix frontend`, and `npm run test:e2e --prefix frontend`. The browser suite owns an isolated server on port 8000 and its own temporary data directory. See [testing](TESTING.md) for setup and [the screenshot guide](screenshots/README.md) for current tracked UI captures.
