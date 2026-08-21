from __future__ import annotations

from pathlib import Path

import uvicorn

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    command.upgrade(Config(PROJECT_ROOT / "alembic.ini"), "head")
    uvicorn.run("mailtrace.main:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
