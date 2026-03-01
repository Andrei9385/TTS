#!/usr/bin/env bash
set -euo pipefail

# One-command installer for Ubuntu 24.04.3 local CPU deployment.
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

SUDO=""
if [ "${EUID}" -ne 0 ]; then
  SUDO="sudo"
fi

echo "[install] Installing system packages..."
$SUDO apt update
$SUDO apt install -y \
  python3 python3-venv python3-pip \
  ffmpeg redis-server git build-essential \
  libsndfile1

echo "[install] Enabling Redis..."
$SUDO systemctl enable --now redis-server

echo "[install] Creating/updating virtualenv..."
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements/base.txt

echo "[install] Installing CPU PyTorch runtime..."
python -m pip install --index-url https://download.pytorch.org/whl/cpu torch torchaudio

echo "[install] Installing F5-TTS runtime..."
python -m pip install git+https://github.com/SWivid/F5-TTS.git

echo "[install] Preparing .env..."
if [ ! -f .env ]; then
  cp .env.example .env
fi

if grep -q '^F5_TTS_COMMAND=' .env; then
  sed -i 's#^F5_TTS_COMMAND=.*#F5_TTS_COMMAND="python scripts/f5_tts_runner_real.py"#' .env
else
  echo 'F5_TTS_COMMAND="python scripts/f5_tts_runner_real.py"' >> .env
fi

if grep -q '^F5_TTS_MODEL_ID=' .env; then
  sed -i 's#^F5_TTS_MODEL_ID=.*#F5_TTS_MODEL_ID="Misha24-10/F5-TTS_RUSSIAN"#' .env
else
  echo 'F5_TTS_MODEL_ID="Misha24-10/F5-TTS_RUSSIAN"' >> .env
fi

echo "[install] Initializing database and storage..."
python scripts/init_db.py

echo "[install] Installing systemd units..."
WEB_UNIT=/etc/systemd/system/tts-web.service
WORKER_UNIT=/etc/systemd/system/tts-worker.service

$SUDO tee "$WEB_UNIT" >/dev/null <<UNIT
[Unit]
Description=Russian TTS MVP Web (FastAPI/Uvicorn)
After=network.target redis-server.service

[Service]
Type=simple
User=${USER}
WorkingDirectory=${PROJECT_DIR}
EnvironmentFile=${PROJECT_DIR}/.env
ExecStart=${PROJECT_DIR}/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

$SUDO tee "$WORKER_UNIT" >/dev/null <<UNIT
[Unit]
Description=Russian TTS MVP Worker (Celery)
After=network.target redis-server.service

[Service]
Type=simple
User=${USER}
WorkingDirectory=${PROJECT_DIR}
EnvironmentFile=${PROJECT_DIR}/.env
ExecStart=${PROJECT_DIR}/.venv/bin/celery -A app.workers.celery_app:celery_app worker --loglevel=INFO
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

$SUDO systemctl daemon-reload
$SUDO systemctl enable --now tts-web.service
$SUDO systemctl enable --now tts-worker.service

echo "[install] Complete."
echo "[install] Open: http://127.0.0.1:8000"
echo "[install] Troubleshooting fallback: set F5_TTS_COMMAND=\"python scripts/f5_tts_runner_stub.py\" in .env"
