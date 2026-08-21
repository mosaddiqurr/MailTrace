# Known Issues

- Docker is not installed on the validation host, so container runtime acceptance is not claimed.
- A new workstation may need `npx playwright install chromium` before its first Playwright run.
- Expiry is enforced when retention settings are saved and when History is loaded; this local application does not run a background scheduler while it is closed.
- Authentication trust positioning is explained, but receiver ownership cannot be proven from message bytes alone.
- FastAPI's current `TestClient` emits an upstream Starlette deprecation warning about the future `httpx2` package. It does not affect the passing application tests.
