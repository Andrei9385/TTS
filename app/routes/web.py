from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import Settings, get_settings
from app.db import get_db_session
from app.models import SynthesisJob, TrainingJob, VoiceProfile
from app.services.audio_service import normalize_audio
from app.services.synthesis_service import create_and_enqueue_synthesis_job
from app.services.training_service import create_and_enqueue_training_job

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a"}
ALLOWED_SYNTHESIS_MODES = {"preview", "full"}


@router.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db_session)) -> HTMLResponse:
    profiles = db.scalars(select(VoiceProfile).order_by(VoiceProfile.created_at.desc())).all()
    recent_jobs = db.scalars(select(SynthesisJob).order_by(SynthesisJob.created_at.desc()).limit(5)).all()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "profiles": profiles,
            "recent_jobs": recent_jobs,
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


@router.get("/synthesize", response_class=HTMLResponse)
def synthesize_page(request: Request, db: Session = Depends(get_db_session)) -> HTMLResponse:
    profiles = db.scalars(select(VoiceProfile).order_by(VoiceProfile.created_at.desc())).all()
    return templates.TemplateResponse(
        request,
        "synthesize.html",
        {
            "profiles": profiles,
            "page_title": "Synthesize",
            "error": request.query_params.get("error"),
        },
    )


@router.post("/synthesize")
def enqueue_synthesis(
    voice_profile_id: int = Form(...),
    input_text: str = Form(...),
    auto_accent_enabled: bool = Form(False),
    mode: str = Form("preview"),
    db: Session = Depends(get_db_session),
) -> RedirectResponse:
    profile = db.get(VoiceProfile, voice_profile_id)
    if profile is None:
        return RedirectResponse(url="/synthesize?error=Unknown+voice+profile", status_code=303)

    if not input_text.strip():
        return RedirectResponse(url="/synthesize?error=Text+is+required", status_code=303)

    if mode not in ALLOWED_SYNTHESIS_MODES:
        return RedirectResponse(url="/synthesize?error=Invalid+mode", status_code=303)

    job = create_and_enqueue_synthesis_job(
        db,
        voice_profile_id=voice_profile_id,
        input_text=input_text,
        auto_accent_enabled=auto_accent_enabled,
        mode=mode,
    )
    return RedirectResponse(url=f"/history?focus_job={job.id}", status_code=303)


@router.get("/history", response_class=HTMLResponse)
def history_page(request: Request, db: Session = Depends(get_db_session)) -> HTMLResponse:
    jobs = _get_history_jobs(db)
    focus_job = request.query_params.get("focus_job")
    return templates.TemplateResponse(
        request,
        "history.html",
        {
            "jobs": jobs,
            "focus_job": focus_job,
            "page_title": "Synthesis History",
        },
    )


@router.get("/history/table", response_class=HTMLResponse)
def history_table_partial(request: Request, db: Session = Depends(get_db_session)) -> HTMLResponse:
    jobs = _get_history_jobs(db)
    return templates.TemplateResponse(
        request,
        "partials/history_rows.html",
        {
            "jobs": jobs,
        },
    )


@router.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, db: Session = Depends(get_db_session)) -> HTMLResponse:
    training_jobs = db.scalars(select(TrainingJob).order_by(TrainingJob.created_at.desc()).limit(100)).all()
    return templates.TemplateResponse(
        request,
        "admin.html",
        {
            "training_jobs": training_jobs,
            "error": request.query_params.get("error"),
            "page_title": "Admin / Fine-tuning",
        },
    )


@router.post("/admin/training-jobs")
def create_training_job(
    dataset_file: UploadFile = File(...),
    notes: str = Form(default=""),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db_session),
) -> RedirectResponse:
    job, error = create_and_enqueue_training_job(
        db,
        settings=settings,
        dataset_file=dataset_file,
        notes=notes,
    )
    if error:
        return RedirectResponse(url=f"/admin?error={error.replace(' ', '+')}", status_code=303)
    return RedirectResponse(url=f"/admin?focus_job={job.id}", status_code=303)


def _get_history_jobs(db: Session) -> list[SynthesisJob]:
    return db.scalars(
        select(SynthesisJob)
        .options(joinedload(SynthesisJob.voice_profile))
        .order_by(SynthesisJob.created_at.desc())
        .limit(200)
    ).all()


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
