from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ALLOWED_DATASET_EXTENSIONS = {".zip", ".jsonl", ".csv", ".txt"}
MAX_DATASET_SIZE_BYTES = 512 * 1024 * 1024  # 512MB conservative limit for local MVP


@dataclass
class DatasetValidationResult:
    is_valid: bool
    error_message: str | None = None


def validate_dataset_file(path: Path) -> DatasetValidationResult:
    if not path.exists() or not path.is_file():
        return DatasetValidationResult(False, "Uploaded dataset file is missing.")

    extension = path.suffix.lower()
    if extension not in ALLOWED_DATASET_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_DATASET_EXTENSIONS))
        return DatasetValidationResult(False, f"Unsupported dataset format: {extension}. Allowed: {allowed}.")

    if path.stat().st_size <= 0:
        return DatasetValidationResult(False, "Dataset file is empty.")

    if path.stat().st_size > MAX_DATASET_SIZE_BYTES:
        return DatasetValidationResult(False, "Dataset file exceeds the 512MB local safety limit.")

    return DatasetValidationResult(True, None)
