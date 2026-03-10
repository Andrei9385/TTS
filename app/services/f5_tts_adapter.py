from __future__ import annotations

import json
import shlex
import subprocess
import sys
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
        command_prefix = self._normalize_command(command_prefix)
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

        self.settings.tmp_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=self.settings.tmp_dir, prefix="f5_tts_") as tmp_dir:
            payload_path = Path(tmp_dir) / "payload.json"
            payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            command = [
                *command_prefix,
                "--payload",
                str(payload_path),
            ]

            effective_timeout = max(int(self.settings.f5_tts_timeout_seconds), 900)
            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=effective_timeout,
                    check=False,
                )
            except FileNotFoundError:
                return F5TTSResult(
                    success=False,
                    output_wav_path=None,
                    return_code=None,
                    stdout="",
                    stderr="",
                    error_message=(
                        "Configured F5-TTS command was not found in PATH or script path is invalid. "
                        f"command={command_prefix}"
                    ),
                    command=command,
                )
            except subprocess.TimeoutExpired as exc:
                return F5TTSResult(
                    success=False,
                    output_wav_path=None,
                    return_code=None,
                    stdout=self._force_text(exc.stdout),
                    stderr=self._force_text(exc.stderr),
                    error_message=f"F5-TTS subprocess timed out after {effective_timeout}s.",
                    command=command,
                )

        stdout = self._force_text(completed.stdout)
        stderr = self._force_text(completed.stderr)

        if completed.returncode != 0:
            return F5TTSResult(
                success=False,
                output_wav_path=None,
                return_code=completed.returncode,
                stdout=stdout,
                stderr=stderr,
                error_message=self._build_subprocess_error(completed.returncode, stdout, stderr),
                command=command,
            )

        if not request.output_wav_path.exists():
            return F5TTSResult(
                success=False,
                output_wav_path=None,
                return_code=completed.returncode,
                stdout=stdout,
                stderr=stderr,
                error_message="F5-TTS subprocess succeeded but output file was not created.",
                command=command,
            )

        return F5TTSResult(
            success=True,
            output_wav_path=request.output_wav_path,
            return_code=completed.returncode,
            stdout=stdout,
            stderr=stderr,
            error_message=None,
            command=command,
        )

    @staticmethod
    def _build_subprocess_error(return_code: int | None, stdout: str, stderr: str) -> str:
        details: list[str] = []
        if return_code is not None:
            details.append(f"return_code={return_code}")

        stderr_tail = (stderr or "").strip()[-500:]
        stdout_tail = (stdout or "").strip()[-300:]

        if stderr_tail:
            details.append(f"stderr_tail={stderr_tail}")
        elif stdout_tail:
            details.append(f"stdout_tail={stdout_tail}")

        suffix = f" ({'; '.join(details)})" if details else ""
        return "F5-TTS subprocess exited with non-zero status." + suffix

    @staticmethod
    def _parse_command(raw_command: str | None) -> list[str]:
        if not raw_command:
            return []
        return shlex.split(raw_command.strip())

    @staticmethod
    def _normalize_command(command: list[str]) -> list[str]:
        if not command:
            return command

        normalized = command.copy()
        if normalized[0] in {"python", "python3"}:
            normalized[0] = sys.executable

        if len(normalized) >= 2 and normalized[1].endswith(".py"):
            script_path = Path(normalized[1])
            if not script_path.is_absolute():
                project_root = Path(__file__).resolve().parents[2]
                normalized[1] = str((project_root / script_path).resolve())

        return normalized

    @staticmethod
    def _force_text(value: str | bytes | None) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value
