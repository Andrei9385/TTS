from __future__ import annotations

from datetime import datetime
from pathlib import Path
import wave

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.models import SynthesisJob, TrainingJob, VoiceProfile
from app.services.auto_accent import build_auto_accent_adapter
from app.services.audio_service import normalize_audio
from app.services.f5_tts_adapter import F5TTSAdapter, F5TTSRequest
from app.services.text_preprocessing import preprocess_text
from app.services.training_runner import TrainingRunRequest, TrainingRunner
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.process_synthesis_job")
def process_synthesis_job(job_id: int) -> dict[str, str | int | None]:
    settings = get_settings()
    adapter = F5TTSAdapter(settings)

    with SessionLocal() as db:
        job = db.get(SynthesisJob, job_id)
        if job is None:
            return {"job_id": job_id, "status": "failed", "error": "Job not found."}

        try:
            job.status = "processing"
            job.started_at = datetime.utcnow()
            db.commit()

            profile = db.get(VoiceProfile, job.voice_profile_id)
            if profile is None:
                return _fail_synthesis_job(db, job, "Voice profile not found.")

            preprocess = preprocess_text(
                text=job.input_text,
                auto_accent_adapter=build_auto_accent_adapter(settings.auto_accent_adapter),
                enable_auto_accent=job.auto_accent_enabled,
            )

            if not preprocess.validation.is_valid:
                job.processed_text = preprocess.stressed_text
                return _fail_synthesis_job(db, job, "; ".join(preprocess.validation.errors))

            output_filename = f"job_{job.id}.wav"
            output_path = settings.outputs_dir / output_filename

            request = F5TTSRequest(
                reference_audio_path=settings.uploads_dir / profile.normalized_filename,
                reference_transcript=profile.transcript,
                target_text=preprocess.final_text,
                output_wav_path=output_path,
            )
            result = adapter.synthesize(request)

            debug_lines: list[str] = []
            if result.command:
                debug_lines.append("runner_command=" + " ".join(result.command))

            if result.success:
                try:
                    _normalize_output_wav(output_path, settings.ffmpeg_bin)
                    debug_lines.append(_probe_wav(output_path))
                except Exception as exc:
                    result = type(result)(
                        success=False,
                        output_wav_path=None,
                        return_code=result.return_code,
                        stdout=result.stdout,
                        stderr=result.stderr,
                        error_message=f"Generated output WAV is invalid/unplayable: {exc}",
                        command=result.command,
                    )

            if result.success and debug_lines:
                print(f"[synthesis-debug] job_id={job.id} {debug_lines[-1]}")

            combined_log = _build_log(preprocess.validation.warnings, result.stdout, result.stderr, debug_lines)
            job.processed_text = preprocess.final_text
            job.worker_log = combined_log[:4000] if combined_log else None

            if result.success:
                job.status = "done"
                job.output_filename = output_filename
                job.error_message = None
            else:
                job.status = "failed"
                job.error_message = result.error_message or "Unknown F5-TTS error."

            job.completed_at = datetime.utcnow()
            db.commit()
            return {
                "job_id": job_id,
                "status": job.status,
                "error": job.error_message,
                "output_filename": job.output_filename,
            }
        except Exception as exc:
            return _fail_synthesis_job(db, job, f"Unexpected synthesis worker error: {exc}")


@celery_app.task(name="app.workers.tasks.process_training_job")
def process_training_job(job_id: int) -> dict[str, str | int | None]:
    settings = get_settings()
    runner = TrainingRunner(settings)

    with SessionLocal() as db:
        job = db.get(TrainingJob, job_id)
        if job is None:
            return {"job_id": job_id, "status": "failed", "error": "Training job not found."}

        try:
            job.status = "processing"
            job.started_at = datetime.utcnow()
            db.commit()

            result = runner.run(
                TrainingRunRequest(
                    training_job_id=job.id,
                    dataset_path=Path(job.dataset_path),
                    notes=job.notes,
                )
            )

            job.runner_log = _build_log(None, result.stdout, result.stderr)[:4000]
            if result.success:
                job.status = "done"
                job.error_message = None
            else:
                job.status = "failed"
                job.error_message = result.error_message or "Unknown training runner error."

            job.completed_at = datetime.utcnow()
            db.commit()
            return {
                "job_id": job.id,
                "status": job.status,
                "error": job.error_message,
            }
        except Exception as exc:
            job.status = "failed"
            job.error_message = f"Unexpected training worker error: {exc}"
            job.completed_at = datetime.utcnow()
            db.commit()
            return {
                "job_id": job.id,
                "status": job.status,
                "error": job.error_message,
            }


def _fail_synthesis_job(db: Session, job: SynthesisJob, message: str) -> dict[str, str | int | None]:
    job.status = "failed"
    job.error_message = message
    job.completed_at = datetime.utcnow()
    db.commit()
    return {"job_id": job.id, "status": job.status, "error": job.error_message}


def _normalize_output_wav(output_path: Path, ffmpeg_bin: str) -> None:
    normalized_path = output_path.with_name(output_path.stem + "_normalized.wav")
    normalize_audio(output_path, normalized_path, ffmpeg_bin)
    normalized_path.replace(output_path)


def _probe_wav(output_path: Path) -> str:
    with wave.open(str(output_path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_rate = wav_file.getframerate()
        sample_width = wav_file.getsampwidth()
        frames = wav_file.getnframes()
    duration = (frames / sample_rate) if sample_rate > 0 else 0.0
    return (
        f"wav_meta path={output_path.name} size={output_path.stat().st_size}B "
        f"channels={channels} sr={sample_rate} sampwidth={sample_width} duration={duration:.3f}s"
    )


def _to_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _build_log(
    warnings: list[str] | None,
    stdout: str | bytes | None,
    stderr: str | bytes | None,
    debug_lines: list[str] | None = None,
) -> str:
    parts: list[str] = []

    normalized_debug = [_to_text(line) for line in (debug_lines or [])]
    if normalized_debug:
        parts.append("Debug: " + " | ".join(normalized_debug))

    normalized_warnings = [_to_text(w) for w in (warnings or [])]
    if normalized_warnings:
        parts.append("Warnings: " + " | ".join(normalized_warnings))

    stdout_text = _to_text(stdout).strip()
    stderr_text = _to_text(stderr).strip()

    if stdout_text:
        parts.append("STDOUT:\n" + stdout_text)
    if stderr_text:
        parts.append("STDERR:\n" + stderr_text)
    return "\n\n".join(parts)
