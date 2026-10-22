# MailTrace interface

The interface uses a dark forensic workspace with a pale-blue email sculpture in the landing hero. The visual direction draws on [Data Signal](https://motionsites.org/prompts/data-signal); the original envelope, source sheets, inspection lens, and delivery paths are rendered procedurally for this project.

## Visual system and workflow

- Near-black backgrounds, charcoal panels, subtle borders, white primary actions, and pale-blue evidence accents. Green, amber, and red indicate evidence status.
- Self-hosted Manrope and DM Mono. Responsive lossless WebP logos and small platform icons are served locally. The [high-resolution logo source](branding/mailtrace-logo.png) is kept outside the public application assets.
- A compact upload/pasted-header panel immediately follows the hero. Reports, history, methodology, and settings share typography, surfaces, navigation, focus treatment, and spacing.
- Reports group assessment, observations, identity, authentication, delivery, content, technical evidence, and limitations, with export access at the top.
- Input controls stack on mobile; report navigation becomes a horizontal row. Large evidence values wrap instead of creating page overflow.

## Motion and resources

The satin envelope, layered source sheets, data particles, synthetic inspection ridges, delivery signals, and scan light move continuously while the hero is visible. There is no motion toggle. Hero motion deliberately continues under `prefers-reduced-motion`; that preference suppresses the other CSS animation and transitions. Reduced-transparency styling uses solid surfaces.

Supporting browsers draw through an OffscreenCanvas worker. The fallback shares cached geometry, batched particles, a capped resolution, and an adaptive frame budget. Drawing suspends outside the visible viewport or in a hidden document and resumes automatically. Route cleanup terminates the worker. Phones render less subpixel detail, and static sections skip rerenders during header entry. No email evidence is sent to the visual worker.

The primary font is preloaded, and hero text appears without a delayed entrance. There are no third-party fonts, runtime visual downloads, or background video files. See [performance verification](PERFORMANCE.md) for measured results.

## Verification

Unit tests check geometry and renderer lifecycle. Desktop/mobile browser checks cover both motion preferences, worker and fallback rendering, off-screen suspension/resume, route cleanup, synthetic evidence analysis, viewport fit, and accessibility across routes. Current screenshots are listed in [the screenshot guide](screenshots/README.md).
