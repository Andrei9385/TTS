from __future__ import annotations

import json
import shlex
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings


@dataclass
class TrainingRunRequest:
    training_job_id: int
    dataset_path: Path
    notes: str | None = None


@dataclass
class TrainingRunResult:
    success: bool
    return_code: int | None
    stdout: str
    stderr: str
    error_message: str | None
    command: list[str]


class TrainingRunner:
    """Pluggable subprocess runner scaffold for future fine-tuning execution."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run(self, request: TrainingRunRequest) -> TrainingRunResult:
        if not request.dataset_path.exists():
            return TrainingRunResult(
                success=False,
                return_code=None,
                stdout="",
                stderr="",
                error_message=f"Dataset path does not exist: {request.dataset_path}",
                command=[],
            )

        command_prefix = self._parse_command(self.settings.training_runner_command)
        if not command_prefix:
            return TrainingRunResult(
                success=False,
                return_code=None,
                stdout="",
                stderr="",
                error_message=(
                    "Training runner is not configured yet. "
                    "Set TRAINING_RUNNER_COMMAND in .env to enable execution."
                ),
                command=[],
            )

        payload = {
            "training_job_id": request.training_job_id,
            "dataset_path": str(request.dataset_path),
            "notes": request.notes,
        }

        self.settings.tmp_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=self.settings.tmp_dir, prefix="training_runner_") as tmp_dir:
            payload_path = Path(tmp_dir) / "payload.json"
            payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            command = [*command_prefix, "--payload", str(payload_path)]
            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=self.settings.training_runner_timeout_seconds,
                    check=False,
                )
            except FileNotFoundError:
                return TrainingRunResult(
                    success=False,
                    return_code=None,
                    stdout="",
                    stderr="",
                    error_message="Configured training runner command not found in PATH.",
                    command=command,
                )
            except subprocess.TimeoutExpired as exc:
                return TrainingRunResult(
                    success=False,
                    return_code=None,
                    stdout=exc.stdout or "",
                    stderr=exc.stderr or "",
                    error_message="Training runner subprocess timed out.",
                    command=command,
                )

        if completed.returncode != 0:
            return TrainingRunResult(
                success=False,
                return_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                error_message="Training runner exited with non-zero status.",
                command=command,
            )

        return TrainingRunResult(
            success=True,
            return_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            error_message=None,
            command=command,
        )

    @staticmethod
    def _parse_command(raw_command: str | None) -> list[str]:
        if not raw_command:
            return []
        return shlex.split(raw_command.strip())
