# TTS

Local CPU-only MVP scaffold for a Russian voice-cloning web app (Ubuntu 24.04.3 focus).

## What is implemented now

- FastAPI + Jinja2 web app
- Voice profile upload + ffmpeg normalization
- SQLite persistence for profiles, synthesis jobs, and training jobs
- Celery + Redis background tasks for synthesis and training scaffolds
- Text preprocessing (`+` stress preservation + validation)
- F5-TTS adapter scaffold (subprocess-based, graceful failure if not configured)
- Admin page scaffold for fine-tuning dataset upload and training job creation

## Ubuntu 24.04.3 setup

### 1) Install system packages

```bash
sudo apt update
sudo apt install -y python3 python3-venv ffmpeg redis-server
```

### 2) Start Redis

```bash
sudo systemctl enable --now redis-server
```

### 3) Bootstrap Python environment

```bash
./scripts/bootstrap.sh
```

### 4) Create `.env`

```bash
cp .env.example .env
```

### 5) Initialize DB + local directories

```bash
source .venv/bin/activate
python scripts/init_db.py
```

### 6) Run the web app

```bash
./scripts/run_web.sh
```

### 7) Run the worker (separate terminal)

```bash
./scripts/run_worker.sh
```

## Main pages

- Profiles: `http://127.0.0.1:8000/profiles`
- Synthesize: `http://127.0.0.1:8000/synthesize`
- History: `http://127.0.0.1:8000/history`
- Admin: `http://127.0.0.1:8000/admin`

## Training scaffold behavior

Admin dataset upload creates a `training_jobs` record and enqueues a Celery task.

- If `TRAINING_RUNNER_COMMAND` is not configured, the job fails gracefully with a clear error.
- Optional stub command for wiring tests:

```bash
TRAINING_RUNNER_COMMAND="python scripts/training_runner_stub.py"
```

## F5-TTS scaffold behavior

- Uses model id `Misha24-10/F5-TTS_RUSSIAN` by default.
- If `F5_TTS_COMMAND` is empty/unavailable, synthesis jobs fail gracefully and persist error details.
- Optional stub command:

```bash
F5_TTS_COMMAND="python scripts/f5_tts_runner_stub.py"
```

## Local operations scripts

- `scripts/bootstrap.sh`
- `scripts/init_db.py`
- `scripts/run_web.sh`
- `scripts/run_worker.sh`
- `scripts/smoke_test.py`

## systemd examples

- `systemd/tts-web.service.example`
- `systemd/tts-worker.service.example`

## Current limitations in this environment

- Dependency installation may be blocked by network/proxy restrictions.
- Without installed dependencies, app startup/worker execution cannot be fully verified in this sandbox.
- Fine-tuning execution is scaffold-only unless a real `TRAINING_RUNNER_COMMAND` is provided.
