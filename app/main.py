from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.db import Base, engine
from app.logging_config import configure_logging
import app.models  # noqa: F401
from app.routes.web import router as web_router
from app.storage import ensure_storage_dirs

settings = get_settings()
ensure_storage_dirs(settings)
configure_logging(settings.logs_dir)
Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.app_name, debug=settings.debug)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(web_router)
