from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic control runner for harness validation.")
    parser.add_argument("--task", required=True)
    parser.add_argument("--venue", default="standard")
    parser.add_argument("--flow", default="default")
    args = parser.parse_args()

    task = json.loads(Path(args.task).read_text(encoding="utf-8"))
    payload = {
        "control": "ok",
        "task_id": task.get("id"),
        "tier": task.get("tier"),
        "venue": args.venue,
        "flow": args.flow,
    }
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
