from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MAILTRACE_", env_file=".env")

    data_dir: Path = Path("data")
    database_url: str | None = None
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)
    max_headers: int = Field(default=500, ge=10)
    max_header_line_bytes: int = Field(default=16_384, ge=256)
    max_mime_depth: int = Field(default=15, ge=1)
    max_mime_parts: int = Field(default=500, ge=1)
    max_attachments: int = Field(default=100, ge=0)
    max_part_bytes: int = Field(default=5 * 1024 * 1024, ge=1024)
    max_decoded_bytes: int = Field(default=20 * 1024 * 1024, ge=1024)
    max_urls: int = Field(default=2000, ge=1)
    analysis_timeout_seconds: float = Field(default=30, ge=1, le=300)
    dns_timeout_seconds: float = Field(default=3.0, ge=0.25, le=15)
    dns_cache_seconds: int = Field(default=900, ge=0)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{(self.data_dir / 'mailtrace.db').as_posix()}"

    @property
    def evidence_dir(self) -> Path:
        return self.data_dir / "evidence"

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
