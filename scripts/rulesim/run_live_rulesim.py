from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orket.rulesim.workload import run_rulesim_v0_sync


def main() -> int:
    parser = argparse.ArgumentParser(description="Run rulesim_v0 synchronously from a JSON config.")
    parser.add_argument("--config", required=True, help="Path to input config JSON")
    parser.add_argument("--workspace", required=True, help="Workspace root path")
    parser.add_argument("--result-out", default="", help="Optional path to write result JSON")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    result = run_rulesim_v0_sync(input_config=config, workspace_path=Path(args.workspace))
    payload = json.dumps(result, sort_keys=True)
    if args.result_out:
        Path(args.result_out).write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
