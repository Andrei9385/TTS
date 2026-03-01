#!/usr/bin/env bash
set -euo pipefail

source .venv/bin/activate

CELERY_LOGLEVEL="${CELERY_LOGLEVEL:-INFO}"
celery -A app.workers.celery_app:celery_app worker --loglevel="$CELERY_LOGLEVEL"
