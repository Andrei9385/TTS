from __future__ import annotations

from pathlib import Path

from app.config import Settings


STORAGE_DIRS: tuple[str, ...] = (
    "uploads_dir",
    "outputs_dir",
    "datasets_dir",
    "tmp_dir",
    "logs_dir",
)


def ensure_storage_dirs(settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    for attr in STORAGE_DIRS:
        path = Path(getattr(settings, attr))
        path.mkdir(parents=True, exist_ok=True)
