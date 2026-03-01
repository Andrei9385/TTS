# TTS

Local CPU-only MVP scaffold for a Russian voice-cloning web app.

## Current scope (implemented)

- FastAPI + Jinja2 web app with static assets
- `.env`-driven configuration
- Logging to console and `data/logs/app.log`
- SQLite initialization with SQLAlchemy models
- Idempotent DB initialization script
- Local storage directory bootstrap
- Voice profile upload page with:
  - profile name
  - optional transcript
  - WAV/MP3/M4A validation
  - ffmpeg normalization to mono 24kHz WAV
  - metadata persistence in SQLite
- Text preprocessing service with:
  - whitespace normalization
  - conservative punctuation normalization
  - stress marker (`+`) preservation
  - Russian text input validation
  - pluggable auto-accent adapter interface + no-op fallback
- F5-TTS subprocess adapter scaffold targeting `Misha24-10/F5-TTS_RUSSIAN` with structured success/failure results

## Project structure

```text
app/
  main.py
  config.py
  logging_config.py
  storage.py
  db.py
  models.py
  routes/web.py
  services/
    audio_service.py
    auto_accent.py
    text_preprocessing.py
    f5_tts_adapter.py
  templates/
  static/
scripts/
  bootstrap.sh
  run_web.sh
  init_db.py
  f5_tts_runner_stub.py
requirements/
  base.txt
data/
  sqlite/
  uploads/
  outputs/
  datasets/
  tmp/
  logs/
.env.example
```

## Quick start

1. Create environment and install deps:

```bash
./scripts/bootstrap.sh
```

2. Copy env file:

```bash
cp .env.example .env
```

3. Initialize database and storage directories:

```bash
source .venv/bin/activate
python scripts/init_db.py
```

4. Run web app:

```bash
./scripts/run_web.sh
```

5. Open browser:

- `http://127.0.0.1:8000`
- Voice profiles: `http://127.0.0.1:8000/profiles`

## F5-TTS adapter scaffold

The F5 adapter is intentionally isolated from routes and uses a safe subprocess command list (no shell execution).

Set in `.env`:

- `F5_TTS_MODEL_ID` (default: `Misha24-10/F5-TTS_RUSSIAN`)
- `F5_TTS_COMMAND` (external command to run inference)
- `F5_TTS_TIMEOUT_SECONDS`

If `F5_TTS_COMMAND` is empty, the adapter returns a graceful structured error. This allows development without blocking on model downloads.

Optional stub command for testing adapter flow:

```bash
F5_TTS_COMMAND="python scripts/f5_tts_runner_stub.py"
```

## Notes

- ffmpeg must be available in PATH (or set `FFMPEG_BIN` in `.env`).
- This stage does not implement synthesis routes, Celery, or training execution.
