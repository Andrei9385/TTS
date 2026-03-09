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
- configure `F5_TTS_COMMAND=".venv/bin/python scripts/f5_tts_runner_real.py"` by default,
- initialize DB,
- enable/start Redis,
- install and start systemd services for web + worker.

After install, open: `http://<IP_МАШИНЫ>:8000` (или `http://127.0.0.1:8000` локально).

Если после обновления в логах всё ещё видно `Uvicorn running on http://127.0.0.1:8000`, обновите unit и перезапустите:

```bash
sudo systemctl daemon-reload
sudo systemctl restart tts-web
systemctl cat tts-web --no-pager
```


## Real synthesis default path

Default `.env` configuration points to the real runner:

```env
F5_TTS_COMMAND=".venv/bin/python scripts/f5_tts_runner_real.py"
F5_TTS_MODEL_ID="Misha24-10/F5-TTS_RUSSIAN"
```

The worker uses the existing adapter/service flow and executes synthesis in background jobs.

CPU synthesis can be slow. Default timeout is set to `F5_TTS_TIMEOUT_SECONDS="900"`.
If needed, increase it in `.env` (for long text or slower CPUs).
For backward compatibility with old `.env` values, runtime enforces a minimum timeout of 900s.

## Optional troubleshooting fallback (stub)

Use stub runner only for debugging:

```bash
sed -i 's#^F5_TTS_COMMAND=.*#F5_TTS_COMMAND=".venv/bin/python scripts/f5_tts_runner_stub.py"#' .env
sudo systemctl restart tts-worker tts-web
```

## First real synthesis test after install

1. Open `http://<IP_МАШИНЫ>:8000/profiles` and upload a short Russian reference WAV/MP3/M4A.
   Важно: заполните transcript (текст из референс-аудио). Профили без transcript теперь не допускаются к синтезу.
2. Open `http://<IP_МАШИНЫ>:8000/synthesize`, select profile, enter Russian text with optional `+` stress marks, submit.
3. Open `http://<IP_МАШИНЫ>:8000/history` and verify job reaches `done`, then play generated audio.

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

Проверьте, что systemd реально применил новый `ExecStart`:

```bash
systemctl cat tts-web --no-pager | sed -n '/ExecStart/p'
ss -ltnp | rg ':8000'
```

Ожидается bind на `0.0.0.0:8000` (или `:::8000`), а не `127.0.0.1:8000`.



Если worker уже запущен и вы меняли `.env`, перезапустите его:

```bash
sudo systemctl restart tts-worker
```


### Если в Celery видите ошибку `Configured F5-TTS command was not found in PATH`

Проверьте команду раннера и перезапустите worker:

```bash
grep ^F5_TTS_COMMAND= .env
# рекомендуемый вид (абсолютный путь):
# F5_TTS_COMMAND="/home/<user>/TTS/.venv/bin/python /home/<user>/TTS/scripts/f5_tts_runner_real.py"

sudo systemctl restart tts-worker
sudo systemctl restart tts-web
```

Проверьте активный unit worker:

```bash
systemctl cat tts-worker --no-pager | sed -n '/ExecStart/p'
```
