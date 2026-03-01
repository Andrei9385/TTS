#!/usr/bin/env bash
set -euo pipefail

source .venv/bin/activate
celery -A app.workers.celery_app:celery_app worker --loglevel=INFO
