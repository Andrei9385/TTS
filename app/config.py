from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Russian Voice Clone TTS MVP"
    environment: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = True

    data_dir: Path = Field(default=Path("data"))
    sqlite_path: Path = Field(default=Path("data/sqlite/app.db"))
    uploads_dir: Path = Field(default=Path("data/uploads"))
    outputs_dir: Path = Field(default=Path("data/outputs"))
    datasets_dir: Path = Field(default=Path("data/datasets"))
    tmp_dir: Path = Field(default=Path("data/tmp"))
    logs_dir: Path = Field(default=Path("data/logs"))

    ffmpeg_bin: str = "ffmpeg"

    f5_tts_model_id: str = "Misha24-10/F5-TTS_RUSSIAN"
    f5_tts_command: str = ""
    f5_tts_timeout_seconds: int = 180

    auto_accent_adapter: str = "noop"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
