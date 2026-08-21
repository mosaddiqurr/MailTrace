FROM node:24.15.0-alpine AS frontend
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12.10-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MAILTRACE_DATA_DIR=/app/data
RUN groupadd --system mailtrace && useradd --system --gid mailtrace --home /app mailtrace
WORKDIR /app
COPY pyproject.toml ./
COPY mailtrace ./mailtrace
COPY alembic ./alembic
COPY alembic.ini ./
COPY --from=frontend /build/frontend/dist ./frontend/dist
RUN pip install --no-cache-dir .
RUN mkdir -p /app/data/evidence && chown -R mailtrace:mailtrace /app
USER mailtrace
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)"
CMD ["sh", "-c", "alembic upgrade head && uvicorn mailtrace.main:app --host 0.0.0.0 --port 8000"]
