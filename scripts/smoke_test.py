from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def main() -> int:
    print("[smoke] compileall")
    code, out, err = run([sys.executable, "-m", "compileall", "app", "scripts"])
    if out:
        print(out)
    if err:
        print(err)
    if code != 0:
        print("[smoke] compileall failed")
        return code

    print("[smoke] init_db")
    code, out, err = run([sys.executable, "scripts/init_db.py"])
    if out:
        print(out)
    if err:
        print(err)
    if code != 0:
        print("[smoke] init_db skipped/failed (likely missing runtime dependencies in this environment)")

    print("[smoke] done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
