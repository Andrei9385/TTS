from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Training external runner stub")
    parser.add_argument("--payload", required=True, help="Path to training payload JSON")
    args = parser.parse_args()

    payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))
    print(f"Training stub invoked for job={payload.get('training_job_id')}")
    print(f"Dataset path: {payload.get('dataset_path')}")
    print("No real fine-tuning executed. Replace this with a real training runner.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
