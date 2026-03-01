from __future__ import annotations

import subprocess
from pathlib import Path

from fastapi import HTTPException


def normalize_audio(input_file: Path, output_file: Path, ffmpeg_bin: str) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        ffmpeg_bin,
        "-y",
        "-i",
        str(input_file),
        "-ac",
        "1",
        "-ar",
        "24000",
        "-sample_fmt",
        "s16",
        str(output_file),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "Audio normalization failed. Please upload a valid audio file "
                "(WAV/MP3/M4A)."
            ),
        )
