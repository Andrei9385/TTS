from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.db import Base, engine
import app.models  # noqa: F401
from app.storage import ensure_storage_dirs


def init_db() -> None:
    settings = get_settings()
    ensure_storage_dirs(settings)
    Base.metadata.create_all(bind=engine)
    print(f"Database initialized at {settings.sqlite_path}")


if __name__ == "__main__":
    init_db()
