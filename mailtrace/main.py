from __future__ import annotations

import logging
import secrets
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import Scope

from mailtrace import __version__
from mailtrace.api import router
from mailtrace.config import get_settings


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404 or "." in Path(path).name:
                raise
            return await super().get_response("index.html", scope)
        if response.status_code == 404 and "." not in Path(path).name:
            return await super().get_response("index.html", scope)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("X-Request-ID", request.state.request_id)
        return response


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = secrets.token_hex(12)
        return await call_next(request)


class LocalRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI, limit: int = 240, window_seconds: int = 60) -> None:
        super().__init__(app)
        self.limit = limit
        self.window_seconds = window_seconds
        self.requests: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path == "/api/health":
            return await call_next(request)
        client = request.client.host if request.client else "local"
        now = time.monotonic()
        entries = self.requests[client]
        while entries and entries[0] < now - self.window_seconds:
            entries.popleft()
        if len(entries) >= self.limit:
            return JSONResponse(status_code=429, content={"detail": "Local request limit exceeded"})
        entries.append(now)
        return await call_next(request)


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="MailTrace API",
        description="Local-first email-header investigation API",
        version=__version__,
        docs_url="/api/docs",
        redoc_url=None,
    )
    origins = [item.strip() for item in settings.cors_origins.split(",") if item.strip()]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "X-Requested-With"],
    )
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(LocalRateLimitMiddleware)
    application.add_middleware(RequestContextMiddleware)
    application.include_router(router)

    @application.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logging.getLogger("mailtrace").exception(
            "request_failed",
            extra={"request_id": request.state.request_id, "path": request.url.path},
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "MailTrace could not complete this request.",
                "code": "unexpected_processing_failure",
                "request_id": request.state.request_id,
            },
        )

    static_dir = Path(__file__).parent.parent / "frontend" / "dist"
    if static_dir.is_dir():
        application.mount("/", SPAStaticFiles(directory=static_dir, html=True), name="frontend")
    return application


app = create_app()
