# AGENTS.md

## Project structure (high level)
- `app/routes/`: FastAPI route handlers (web UI endpoints only)
- `app/services/`: business logic/adapters (audio, preprocessing, synthesis/training orchestration)
- `app/workers/`: Celery app + async task entrypoints
- `app/templates/`: Jinja2 templates and HTMX partials
- `scripts/`: local operations scripts (bootstrap, init, run, smoke test)
- `systemd/`: local example unit files

## Key commands
- Bootstrap env: `./scripts/bootstrap.sh`
- Init DB/directories: `python scripts/init_db.py`
- Run web app: `./scripts/run_web.sh`
- Run worker: `./scripts/run_worker.sh`
- Smoke test: `python scripts/smoke_test.py`

## Validation commands
- `python -m compileall app scripts`
- `python scripts/init_db.py`
- `python scripts/smoke_test.py`

## Coding conventions for this repo
- Keep routes thin; move heavy logic to `app/services` and worker tasks.
- Do not run heavy synthesis/training directly in web requests.
- Use safe subprocess execution (`subprocess.run` with command arrays, `shell=False`).
- Keep local-only file handling conservative (sanitize names, enforce extensions/limits).
- Prefer simple, explicit types and dataclasses for result objects.
- Keep changes minimal and focused on requested phase.
