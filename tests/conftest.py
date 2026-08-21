from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from mailtrace import models  # noqa: F401
from mailtrace.config import Settings
from mailtrace.db import Base


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    value = Settings(data_dir=tmp_path / "data")
    value.ensure_directories()
    return value


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
