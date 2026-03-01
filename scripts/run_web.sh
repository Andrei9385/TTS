#!/usr/bin/env bash
set -euo pipefail

source .venv/bin/activate

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
RELOAD_FLAG="${RELOAD_FLAG:---reload}"

uvicorn app.main:app --host "$HOST" --port "$PORT" $RELOAD_FLAG
