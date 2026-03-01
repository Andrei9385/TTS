from __future__ import annotations

import logging
from logging.config import dictConfig
from pathlib import Path


def configure_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "level": "INFO",
                },
                "file": {
                    "class": "logging.FileHandler",
                    "formatter": "default",
                    "filename": str(log_file),
                    "level": "INFO",
                },
            },
            "root": {
                "handlers": ["console", "file"],
                "level": "INFO",
            },
        }
    )

    logging.getLogger(__name__).info("Logging configured. Log file: %s", log_file)
