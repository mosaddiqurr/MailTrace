# Decisions

- Preserve the case model for compatibility while making evidence analyses the primary UI/API resource.
- Keep processing synchronous because bounded local parsing completes quickly; return the persisted completed state through the `202` analysis contract and show an honest indeterminate UI state.
- Never render message HTML. Provide a plain-text preview derived without loading remote resources.
- Keep original evidence until explicit deletion by default; 7/30/90-day preferences are persisted for future scheduled cleanup.
- Keep DNS off by default and label enabled lookups as current context, never authentication verification.
- Use deterministic labels and categorical confidence rather than numeric threat scores.
- Draw the decorative email sculpture in an OffscreenCanvas worker where supported, with the same optimized renderer as a fallback. Keep email evidence out of the visual worker, suspend drawing when invisible, and dispose the worker on navigation.
- Keep high-resolution design sources in documentation and serve only right-sized, self-hosted assets to the UI.
