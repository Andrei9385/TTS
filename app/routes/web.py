from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db_session
from app.models import VoiceProfile
from app.services.audio_service import normalize_audio

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a"}


@router.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db_session)) -> HTMLResponse:
    profiles = db.scalars(select(VoiceProfile).order_by(VoiceProfile.created_at.desc())).all()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "profiles": profiles,
            "page_title": "Home",
            "error": None,
        },
    )


@router.get("/profiles", response_class=HTMLResponse)
def profiles_page(request: Request, db: Session = Depends(get_db_session)) -> HTMLResponse:
    profiles = db.scalars(select(VoiceProfile).order_by(VoiceProfile.created_at.desc())).all()
    return templates.TemplateResponse(
        request,
        "profiles.html",
        {
            "profiles": profiles,
            "page_title": "Voice Profiles",
            "error": None,
        },
    )


@router.post("/profiles", response_class=HTMLResponse)
def upload_profile(
    request: Request,
    name: str = Form(...),
    transcript: str = Form(default=""),
    audio_file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db_session),
) -> HTMLResponse:
    if not name.strip():
        return _render_profiles_with_error(request, db, "Profile name is required.")

    source_name = Path(audio_file.filename or "").name
    extension = Path(source_name).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        return _render_profiles_with_error(request, db, "Only WAV, MP3, or M4A files are supported.")

    profile_id = uuid4().hex
    source_filename = f"{profile_id}_source{extension}"
    normalized_filename = f"{profile_id}_normalized.wav"
    source_path = settings.uploads_dir / source_filename
    normalized_path = settings.uploads_dir / normalized_filename

    try:
        with source_path.open("wb") as dest:
            shutil.copyfileobj(audio_file.file, dest)
        normalize_audio(source_path, normalized_path, settings.ffmpeg_bin)

        voice_profile = VoiceProfile(
            name=name.strip(),
            source_filename=source_filename,
            normalized_filename=normalized_filename,
            transcript=transcript.strip() or None,
        )
        db.add(voice_profile)
        db.commit()
    except Exception as exc:
        db.rollback()
        if source_path.exists():
            source_path.unlink(missing_ok=True)
        if normalized_path.exists():
            normalized_path.unlink(missing_ok=True)
        return _render_profiles_with_error(
            request,
            db,
            f"Could not save profile: {exc}",
        )
    finally:
        audio_file.file.close()

    return RedirectResponse(url="/profiles", status_code=303)


def _render_profiles_with_error(request: Request, db: Session, message: str) -> HTMLResponse:
    profiles = db.scalars(select(VoiceProfile).order_by(VoiceProfile.created_at.desc())).all()
    return templates.TemplateResponse(
        request,
        "profiles.html",
        {
            "profiles": profiles,
            "page_title": "Voice Profiles",
            "error": message,
        },
        status_code=400,
    )
