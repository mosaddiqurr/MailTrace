# Run Locally

Install Python 3.12 and Node.js 24. Run `powershell -ExecutionPolicy Bypass -File scripts/run-local.ps1` for the built application at `http://127.0.0.1:8000`, or add `-Development` for Vite at `http://127.0.0.1:5173` with the coordinated API on port 8000.

The script creates an isolated `.venv` when needed, applies Alembic migrations, starts the API, and starts the correct UI. Press Ctrl+C to stop. No global Python packages are required.
