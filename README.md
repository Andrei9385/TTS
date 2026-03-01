# TTS

Local CPU-only MVP of a Russian voice-cloning web app on Ubuntu 24.04.3 using FastAPI + Celery + Redis + F5-TTS.

## One-command install (real F5-TTS default)

```bash
./scripts/install_local.sh
```

This installer will:
- install required Ubuntu packages,
- create/update `.venv`,
- install Python dependencies,
- install CPU PyTorch + real F5-TTS runtime,
- create `.env` if missing,
- configure `F5_TTS_COMMAND="python scripts/f5_tts_runner_real.py"` by default,
- initialize DB,
- enable/start Redis,
- install and start systemd services for web + worker.

After install, open: `http://127.0.0.1:8000`

## Real synthesis default path

Default `.env` configuration points to the real runner:

```env
F5_TTS_COMMAND="python scripts/f5_tts_runner_real.py"
F5_TTS_MODEL_ID="Misha24-10/F5-TTS_RUSSIAN"
```

The worker uses the existing adapter/service flow and executes synthesis in background jobs.

## Optional troubleshooting fallback (stub)

Use stub runner only for debugging:

```bash
sed -i 's#^F5_TTS_COMMAND=.*#F5_TTS_COMMAND="python scripts/f5_tts_runner_stub.py"#' .env
sudo systemctl restart tts-worker tts-web
```

## First real synthesis test after install

1. Open `http://127.0.0.1:8000/profiles` and upload a short Russian reference WAV/MP3/M4A.
2. Open `http://127.0.0.1:8000/synthesize`, select profile, enter Russian text with optional `+` stress marks, submit.
3. Open `http://127.0.0.1:8000/history` and verify job reaches `done`, then play generated audio.

## Manual run commands (without systemd)

```bash
./scripts/bootstrap.sh
cp .env.example .env
python scripts/init_db.py
./scripts/run_web.sh
./scripts/run_worker.sh
```

## Current environment limitations (this sandbox)

- Network/proxy restrictions may block dependency installation.
- Because dependencies are not installable here, full runtime verification of real F5 synthesis cannot be completed in this sandbox.

### Exact Ubuntu 24.04.3 verification commands

Run these on a real machine after install:

```bash
python scripts/init_db.py
systemctl status tts-web --no-pager
systemctl status tts-worker --no-pager
curl -I http://127.0.0.1:8000/
```

Then execute the first real synthesis test from UI as described above.
