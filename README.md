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
  services/audio_service.py
  templates/
  static/
scripts/
  bootstrap.sh
  run_web.sh
  init_db.py
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

## Notes

- ffmpeg must be available in PATH (or set `FFMPEG_BIN` in `.env`).
- This stage does not implement synthesis, Celery, or training execution.
