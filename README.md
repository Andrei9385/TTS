# TTS

Local CPU-only MVP scaffold for a Russian voice-cloning web app.

## Current scope (implemented)

- FastAPI + Jinja2 web app with static assets
- `.env`-driven configuration
- Logging to console and `data/logs/app.log`
- SQLite initialization with SQLAlchemy models
- Voice profile upload with ffmpeg normalization (WAV/MP3/M4A)
- Text preprocessing service (whitespace/punctuation normalization, `+` stress preservation, Russian text validation)
- Pluggable auto-accent adapter interface with a no-op fallback
- F5-TTS subprocess adapter scaffold for model `Misha24-10/F5-TTS_RUSSIAN`
- Celery + Redis background flow for synthesis jobs
- Synthesize page (enqueue only) and History page with polling updates

## Project structure

```text
app/
  main.py
  config.py
  db.py
  models.py
  routes/web.py
  services/
    audio_service.py
    auto_accent.py
    text_preprocessing.py
    f5_tts_adapter.py
    synthesis_service.py
  workers/
    celery_app.py
    tasks.py
  templates/
  static/
scripts/
  bootstrap.sh
  run_web.sh
  run_worker.sh
  init_db.py
  f5_tts_runner_stub.py
requirements/
  base.txt
.env.example
```

## Quick start

1. Bootstrap Python environment:

```bash
./scripts/bootstrap.sh
```

2. Create env file:

```bash
cp .env.example .env
```

3. Ensure Redis is running (example Ubuntu):

```bash
sudo systemctl start redis-server
```

4. Initialize DB and data directories:

```bash
source .venv/bin/activate
python scripts/init_db.py
```

5. Start web app:

```bash
./scripts/run_web.sh
```

6. Start Celery worker (separate terminal):

```bash
./scripts/run_worker.sh
```

7. Open browser:

- `http://127.0.0.1:8000/synthesize`
- `http://127.0.0.1:8000/history`

## F5-TTS adapter notes

Set these `.env` keys:

- `F5_TTS_MODEL_ID` (default `Misha24-10/F5-TTS_RUSSIAN`)
- `F5_TTS_COMMAND` (external runner command)
- `F5_TTS_TIMEOUT_SECONDS`

If `F5_TTS_COMMAND` is empty/unavailable, synthesis jobs fail gracefully with a clear DB error.

Optional scaffold runner:

```bash
F5_TTS_COMMAND="python scripts/f5_tts_runner_stub.py"
```

## Notes

- Heavy synthesis is executed only by Celery workers.
- Training execution is intentionally not implemented at this stage.
