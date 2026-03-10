from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import TrainingJob
from app.services.training_validation import validate_dataset_file
from app.workers.tasks import process_training_job


def create_and_enqueue_training_job(
    db: Session,
    *,
    settings: Settings,
    dataset_file: UploadFile,
    notes: str,
) -> tuple[TrainingJob | None, str | None]:
    source_name = Path(dataset_file.filename or "").name
    if not source_name:
        return None, "Dataset file name is missing."

    dataset_id = uuid4().hex
    target_name = f"{dataset_id}_{source_name}"
    datasets_upload_dir = settings.datasets_dir / "uploads"
    datasets_upload_dir.mkdir(parents=True, exist_ok=True)
    target_path = datasets_upload_dir / target_name

    try:
        with target_path.open("wb") as destination:
            while True:
                chunk = dataset_file.file.read(1024 * 1024)
                if not chunk:
                    break
                destination.write(chunk)

        validation = validate_dataset_file(target_path)
        if not validation.is_valid:
            target_path.unlink(missing_ok=True)
            return None, validation.error_message

        job = TrainingJob(
            status="queued",
            dataset_path=str(target_path),
            dataset_name=source_name,
            notes=notes.strip() or None,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        try:
            process_training_job.delay(job.id)
        except Exception as exc:
            job.status = "failed"
            job.error_message = f"Failed to enqueue training job: {exc}"
            db.commit()
            db.refresh(job)

        return job, None
    finally:
        dataset_file.file.close()
