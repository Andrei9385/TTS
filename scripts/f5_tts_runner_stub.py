from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="F5-TTS external runner stub")
    parser.add_argument("--payload", required=True, help="Path to payload JSON from adapter")
    args = parser.parse_args()

    payload_path = Path(args.payload)
    payload = json.loads(payload_path.read_text(encoding="utf-8"))

    print(
        "Stub runner invoked for model "
        f"{payload.get('model_id')} with reference audio {payload.get('reference_audio_path')}"
    )
    print(
        "No real synthesis executed in this scaffold. "
        "Replace this script/command with real F5-TTS integration."
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
