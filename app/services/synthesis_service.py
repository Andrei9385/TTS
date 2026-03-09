from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import SynthesisJob
from app.workers.tasks import process_synthesis_job


def create_and_enqueue_synthesis_job(
    db: Session,
    *,
    voice_profile_id: int,
    input_text: str,
    auto_accent_enabled: bool,
    mode: str,
) -> SynthesisJob:
    job = SynthesisJob(
        voice_profile_id=voice_profile_id,
        input_text=input_text.strip(),
        auto_accent_enabled=auto_accent_enabled,
        mode=mode,
        status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        process_synthesis_job.delay(job.id)
    except Exception as exc:
        job.status = "failed"
        job.error_message = f"Failed to enqueue job: {exc}"
        db.commit()
        db.refresh(job)

    return job
