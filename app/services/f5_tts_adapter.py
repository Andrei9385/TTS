from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings


@dataclass
class F5TTSRequest:
    reference_audio_path: Path
    target_text: str
    output_wav_path: Path
    reference_transcript: str | None = None


@dataclass
class F5TTSResult:
    success: bool
    output_wav_path: Path | None
    return_code: int | None
    stdout: str
    stderr: str
    error_message: str | None
    command: list[str]


class F5TTSAdapter:
    """Subprocess-based F5-TTS adapter scaffold.

    The adapter is intentionally conservative and environment-safe:
    - no shell execution
    - explicit command array
    - timeout support
    - structured success/failure result
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def synthesize(self, request: F5TTSRequest) -> F5TTSResult:
        if not request.reference_audio_path.exists():
            return F5TTSResult(
                success=False,
                output_wav_path=None,
                return_code=None,
                stdout="",
                stderr="",
                error_message=f"Reference audio not found: {request.reference_audio_path}",
                command=[],
            )

        output_dir = request.output_wav_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)

        command_prefix = self._parse_command(self.settings.f5_tts_command)
        if not command_prefix:
            return F5TTSResult(
                success=False,
                output_wav_path=None,
                return_code=None,
                stdout="",
                stderr="",
                error_message=(
                    "F5-TTS command is not configured. Set F5_TTS_COMMAND in .env "
                    "to enable external inference runner integration."
                ),
                command=[],
            )

        payload = {
            "model_id": self.settings.f5_tts_model_id,
            "reference_audio_path": str(request.reference_audio_path),
            "reference_transcript": request.reference_transcript,
            "target_text": request.target_text,
            "output_wav_path": str(request.output_wav_path),
        }

        with tempfile.TemporaryDirectory(dir=self.settings.tmp_dir, prefix="f5_tts_") as tmp_dir:
            payload_path = Path(tmp_dir) / "payload.json"
            payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            command = [
                *command_prefix,
                "--payload",
                str(payload_path),
            ]

            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=self.settings.f5_tts_timeout_seconds,
                    check=False,
                )
            except FileNotFoundError:
                return F5TTSResult(
                    success=False,
                    output_wav_path=None,
                    return_code=None,
                    stdout="",
                    stderr="",
                    error_message="Configured F5-TTS command was not found in PATH.",
                    command=command,
                )
            except subprocess.TimeoutExpired as exc:
                return F5TTSResult(
                    success=False,
                    output_wav_path=None,
                    return_code=None,
                    stdout=exc.stdout or "",
                    stderr=exc.stderr or "",
                    error_message="F5-TTS subprocess timed out.",
                    command=command,
                )

        if completed.returncode != 0:
            return F5TTSResult(
                success=False,
                output_wav_path=None,
                return_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                error_message="F5-TTS subprocess exited with non-zero status.",
                command=command,
            )

        if not request.output_wav_path.exists():
            return F5TTSResult(
                success=False,
                output_wav_path=None,
                return_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                error_message="F5-TTS subprocess succeeded but output file was not created.",
                command=command,
            )

        return F5TTSResult(
            success=True,
            output_wav_path=request.output_wav_path,
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
        return [segment for segment in raw_command.strip().split(" ") if segment]
